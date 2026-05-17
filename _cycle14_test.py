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
    ans = str(d.get("answer", r.get("errors", "?")) if d else "no data")[:72]
    print(f"{'PASS' if ok else 'FAIL'} exp={exp:<26} got={intent:<26} | {q[:55]}")
    if not ok:
        print(f"   {ans}")
    return ok

tests = [
    # Batch regresiones de todos los ciclos
    ("top 3 de candidatos en Suecia", "geo"),
    ("resultados en Buenos Aires", "ambiguous"),
    ("cuantos votos saco Keiko a nivel nacional", "candidate"),
    ("¿quién ganó la elección?", "unknown"),
    ("como le fue a Forsyth en la primera vuelta", "candidate"),
    ("Keiko y Lopez Aliaga en Puno", "multi_candidate"),
    ("quien saco mas Keiko o Aliaga?", "multi_candidate"),
    ("comparar a Keiko con Aliaga en Puno", "multi_candidate"),
    ("nulos en lima", "geo_domestic"),
    ("top 20 en Peru", "nacional"),
    # Edge: nombres muy cortos
    ("Ce en Lima", "geo_domestic"),  # "Ce" podría ser un candidato pero también falla como nombre válido
    # Edge: nombres con números
    ("Forsyth 2026 Lima", "geo_domestic"),  # año como año, no mesa
    # Edge: queries de dos palabras
    ("votos Keiko", "candidate"),
    ("Aliaga Lima", "geo_domestic"),  # sin verbo → geo
    # Edge: query mixto candidato+geo extranjero
    ("Keiko en Tokio", "candidate"),   # nombre válido de candidato → candidate con scope extranjero
    ("Aliaga en Paris", "candidate"),   # mismo caso
    # Edge: geo extranjero con candidato
    ("cuantos votos saco Forsyth en Alemania", "candidate"),
    # Multi-candidato extremo  
    ("Keiko vs Aliaga vs Nieto", "multi_candidate"),
    # Ambigua real
    ("Lima", "geo_domestic"),
    ("900100", "mesa"),
]
ok_count = sum(run(q, e) for q, e in tests)
print(f"\n{ok_count}/{len(tests)} PASS  {len(tests)-ok_count}/{len(tests)} FAIL")
