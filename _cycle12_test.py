import sys, io, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
logging.disable(logging.CRITICAL)
from onpe_mcp.server import onpe_chat

def run(q, exp):
    r = onpe_chat(q)
    d = r.get("data") or {}
    intent = d.get("intent", "ERR") if d else (r.get("errors") or [{}])[0].get("code", "ERR")
    ok = intent == exp
    ans = str(d.get("answer", r.get("errors", "?")) if d else "no data")[:70]
    print(f"{'PASS' if ok else 'FAIL'} exp={exp:<26} got={intent:<26} | {q[:55]}")
    if not ok:
        print(f"   {ans}")
    return ok

tests = [
    # Regresiones de ciclos anteriores — todo debe seguir pasando
    ("cuantos votos saco Keiko a nivel nacional", "candidate"),
    ("top 3 de candidatos en Suecia", "geo"),
    ("top 3 en Loreto", "geo_domestic"),
    ("cuantos votos obtuvo nieto en arequipa", "candidate"),
    ("cuantos votos obtuvo Rafael Lopez Aliaga en puno", "candidate"),
    ("senadores top 10 para Cuzco", "legislative_top_candidate"),
    ("Keiko y Lopez Aliaga en Puno", "multi_candidate"),
    ("comparar a Keiko con Aliaga en Puno", "multi_candidate"),
    ("nulos en lima", "geo_domestic"),
    ("top 20 en Peru", "nacional"),
    # Nuevas: candidatos con artículos y conectores
    ("cuántos votos tuvo el candidato Urresti en Lima", "candidate"),
    ("resultado del candidato Forsyth en Ica", "candidate"),
    # Geo con preposición
    ("resultados para el departamento de Loreto", "geo_domestic"),
    ("cuántos votos hubo en la provincia de Puno", "geo_domestic"),
    # Multi-candidato sin geo explícita
    ("cuántos votos sacó Fujimori versus Aliaga?", "multi_candidate"),
    ("diferencia de votos entre Sánchez y Forsyth", "multi_candidate"),
    # Candidato con alias cultural
    ("sombrero cuantos votos saco en Lima", "candidate"),
    ("el del sombrero en Arequipa", "candidate"),
    # Nacional edge cases
    ("resultados finales de la eleccion", "nacional"),
    ("ganadores de la primera vuelta", "nacional"),
]
ok_count = sum(run(q, e) for q, e in tests)
print(f"\n{ok_count}/{len(tests)} PASS  {len(tests)-ok_count}/{len(tests)} FAIL")
