import sys, io, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
logging.disable(logging.CRITICAL)
from onpe_mcp.server import onpe_chat

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
    # Usuario real: queries cortas muy naturales
    ("Dame resultados Lima", "geo_domestic"),
    ("quiero ver Cusco", "geo_domestic"),
    ("Aliaga qué tal le fue", "candidate"),
    ("Fujimori resultados", "candidate"),
    ("a ver Lima", "geo_domestic"),
    # Preguntas retóricas / periodísticas
    ("qué pasó en Puno?", "geo_domestic"),
    ("cómo le fue al país?", "nacional"),
    ("quiénes son los más votados?", "nacional"),
    # Candidatos con appellidos compuestos
    ("cuantos votos saco Lopez Aliaga en Moquegua", "candidate"),
    ("Lopez Aliaga en Moquegua", "candidate"),
    ("Keiko Fujimori en Piura cuantos votos", "candidate"),
    # Extranjero directo
    ("España resultados", "geo"),
    ("votos en Tokio", "geo"),  # solo lugar extranjero, sin candidato
    ("resultados en Berlín", "geo"),
    # Regresión defensiva
    ("top 3 en Loreto", "geo_domestic"),
    ("top 3 de candidatos en Suecia", "geo"),
    ("mesa 900100", "mesa"),
    ("6 dígitos: consulta la mesa 900100", "mesa"),
    # Consulta de datos específicos
    ("cuántos votos en blanco hubo en Lima", "geo_domestic"),
    ("votos impugnados en Arequipa", "geo_domestic"),
]
ok_count = sum(run(q, e) for q, e in tests)
print(f"\n{ok_count}/{len(tests)} PASS  {len(tests)-ok_count}/{len(tests)} FAIL")
