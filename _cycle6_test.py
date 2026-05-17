import sys, io, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
logging.disable(logging.CRITICAL)
from onpe_mcp.server import onpe_chat

tests = [
    # Regresiones de ciclos anteriores
    ("Lopez Aliaga y Fujimori cuantos votos sacaron", "multi_candidate"),
    ("cuantos votos saco Keiko en Iquitos", "candidate"),
    ("cuantos votos saco Nieto en Arequipa", "candidate"),
    ("top 3 candidatos en Suecia", "geo"),
    ("resultados en Buenos Aires", "ambiguous"),
    ("senadores para Puno", "legislative_top_candidate"),
    ("mesa 900100", "mesa"),
    ("resultados en Puno", "geo_domestic"),
    # Nuevas variantes extremas
    ("Acuna Lima votos", "candidate"),
    ("Forsyth Callao resultados", "candidate"),
    ("Keiko Lima porcentaje", "candidate"),
    ("Aliaga frente a Cerrón en Puno", "multi_candidate"),
    ("Vizcarra contra Acuna en Ica", "multi_candidate"),
    ("cuantos votos obtuvo Aliaga en el interior del pais", "candidate"),
    ("votos blancos en arequipa", "geo_domestic"),  # blancos no es candidato
    ("nulos en lima", "geo_domestic"),
    ("viciados en Puno", "geo_domestic"),
    ("cuantos votos en blanco hubo en Lima", "geo_domestic"),
    ("top 20 en Peru", "nacional"),
    ("ranking nacional de candidatos", "nacional"),
]
ok=0; fail=0
for q, exp in tests:
    r = onpe_chat(q)
    d = r.get("data") or {}
    intent = d.get("intent", "ERR")
    ok += int(intent == exp)
    fail += int(intent != exp)
    status = "PASS" if intent == exp else "FAIL"
    ans = str(d.get("answer", "?"))[:70]
    print(f"{status} exp={exp:<26} got={intent:<26} | {q[:50]}")
    if "FAIL" in status:
        print(f"   {ans}")
print(f"\n{ok}/20 PASS  {fail}/20 FAIL")
