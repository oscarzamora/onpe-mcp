import sys, io, logging
if __name__ == '__main__':  # encoding fix only for direct run, not pytest
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
logging.disable(logging.CRITICAL)
from onpe_mcp.server import onpe_chat, _strip_filler, _norm

# Primero verificar que _strip_filler funciona correctamente
filler_tests = [
    ("a ver cuántos votos tuvo Keiko", "cuántos votos tuvo Keiko"),
    ("dime los resultados en Arequipa", "los resultados en Arequipa"),
    ("me puedes decir los resultados de Lima", "los resultados de Lima"),
    ("quiero saber cuantos votos saco Aliaga en Puno", "cuantos votos saco Aliaga en Puno"),
    ("oye, cuanto fue en Tacna", "cuanto fue en Tacna"),
    ("por favor dime resultados Lima", "resultados Lima"),
    ("cuéntame sobre Forsyth en Ica", "sobre Forsyth en Ica"),
]
print("=== _strip_filler tests ===")
filler_ok = 0
for inp, exp in filler_tests:
    result = _strip_filler(inp)
    ok = _norm(result) == _norm(exp)
    filler_ok += int(ok)
    print(f"  {'OK' if ok else 'XX'} {inp!r} -> {result!r}")

print(f"\n{filler_ok}/{len(filler_tests)} filler strips OK\n")

# Ahora routing
def run(q, exp):
    r = onpe_chat(q)
    d = r.get("data") or {}
    intent = d.get("intent", "ERR") if d else (r.get("errors") or [{}])[0].get("code", "ERR")
    ok = intent == exp
    ans = str(d.get("answer", "no-ans") if d else "no data")[:72]
    print(f"{'PASS' if ok else 'FAIL'} exp={exp:<26} got={intent:<26} | {q[:55]}")
    if not ok:
        print(f"   {ans}")
    return ok

tests = [
    # Lenguaje 100% natural con muletillas
    ("a ver qué tal le fue a Forsyth en Ica", "candidate"),
    ("me puedes decir cuantos votos tuvo Keiko en Lima?", "candidate"),
    ("dime los resultados de Arequipa por favor", "geo_domestic"),
    ("quiero saber cuantos votos saco Nieto en primera vuelta", "candidate"),
    ("oye, cuánto saco Aliaga en Puno?", "candidate"),
    ("cuéntame los resultados del exterior", "geo_foreign_summary"),
    # Frases más largas con verbos coloquiales
    ("me dices cuántos votos tuvo el candidato Urresti en Lima?", "candidate"),
    ("puedes mostrarme los resultados de Cusco?", "geo_domestic"),
    ("quisiera ver el top 5 de candidatos", "nacional"),
    ("necesito saber quiénes ganaron en Madre de Dios", "geo_domestic"),
    # Variantes con tildes / sin tildes intercaladas
    ("cuantos votos obtuvo Fujimori en la primera vuelta", "candidate"),
    ("cuántos votos obtuvo Fujimori en primera vuelta", "candidate"),
    ("cuantos votos sacó Keiko en todo el Peru", "candidate"),
    # Regresiones core
    ("top 3 de candidatos en Suecia", "geo"),
    ("senadores top 10 para Cuzco", "legislative_top_candidate"),
    ("nulos en lima", "geo_domestic"),
    ("quien saco mas Keiko o Aliaga?", "multi_candidate"),
    ("900100", "mesa"),
    # Lenguaje natural extremo
    ("quisiera saber si Forsyth le ganó a Aliaga en Tacna", "multi_candidate"),
    ("dime quién ganó en Junín", "geo_domestic"),
]
ok_count = sum(run(q, e) for q, e in tests)
print(f"\n{ok_count}/{len(tests)} PASS  {len(tests)-ok_count}/{len(tests)} FAIL")
