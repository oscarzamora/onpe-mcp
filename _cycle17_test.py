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
        ans = str(d.get("answer", "no-ans") if d else "no data")[:70]
        print(f"FAIL exp={exp:<26} got={intent:<26} | {q[:55]}")
        print(f"   {ans}")
    else:
        print(f"PASS exp={exp:<26} got={intent:<26} | {q[:55]}")
    return ok

tests = [
    # ── Regresiones de todos los ciclos ──────────────────────────────────────
    ("top 3 de candidatos en Suecia", "geo"),
    ("top 3 en Loreto", "geo_domestic"),
    ("resultados en Buenos Aires", "ambiguous"),
    ("cuantos votos saco Keiko a nivel nacional", "candidate"),
    ("¿quién ganó la elección?", "unknown"),
    ("como le fue a Forsyth en la primera vuelta", "candidate"),
    ("Keiko y Lopez Aliaga en Puno", "multi_candidate"),
    ("quien saco mas Keiko o Aliaga?", "multi_candidate"),
    ("nulos en lima", "geo_domestic"),
    ("top 20 en Peru", "nacional"),
    ("cuantos votos obtuvo nieto en arequipa", "candidate"),
    ("Lopez Aliaga en Moquegua", "candidate"),
    ("castillo votos en Puno", "candidate"),
    ("900100", "mesa"),
    ("senadores top 10 para Cuzco", "legislative_top_candidate"),
    # ── Nuevas con normalización y lenguaje natural ──────────────────────────
    ("a ver cuántos votos sacó Keiko en Lima", "candidate"),
    ("me puedes decir los resultados de Tacna", "geo_domestic"),
    ("quisiera saber si Forsyth le ganó a Aliaga en Tacna", "multi_candidate"),
    ("cuántos votos en blanco hubo en Lima", "geo_domestic"),
    ("puedes mostrarme los resultados de Cusco", "geo_domestic"),
]
ok_count = sum(run(q, e) for q, e in tests)
print(f"\n{ok_count}/{len(tests)} PASS  {len(tests)-ok_count}/{len(tests)} FAIL")
