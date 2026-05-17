import sys, io, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
logging.disable(logging.CRITICAL)
from onpe_mcp.server import onpe_chat

tests = [
    # Deep regression: todos los ciclos anteriores mezclados
    ("quien saco mas Keiko o Aliaga?", "multi_candidate"),
    ("Fujimori Lima resultados primera vuelta", "candidate"),
    ("como van las elecciones en Arequipa", "geo_domestic"),
    ("top 20 en Peru", "nacional"),
    ("dame el top 5", "nacional"),
    ("ranking nacional de candidatos", "nacional"),
    ("nulos en lima", "geo_domestic"),
    ("comparar a Keiko con Aliaga en Puno", "multi_candidate"),
    ("votos de peruanos en Chile", "geo"),
    ("senadores para Puno", "legislative_top_candidate"),
    # Nuevas: candidatos con apodos/fragmentos
    ("Keikooo cuantos votos tuvo", "candidate"),  # typo
    ("aliaga en lima cuantos votos", "candidate"),
    ("lopez aliaga lima", "geo_domestic"),  # sin verbo ni "en" → geo_domestic es razonable
    # Nuevas: frases complejas con fecha
    ("en las elecciones del 2026 cuantos votos tuvo Keiko en Lima", "candidate"),
    ("primera vuelta 2026 resultados Arequipa", "geo_domestic"),
    # Geo extranjero con "de"
    ("resultados de peruanos en el exterior", "geo_foreign_summary"),
    ("votos de la diaspora en Italia", "geo"),
    # Multi-candidato con "también"
    ("cuantos votos tuvo Keiko y tambien Aliaga", "multi_candidate"),
    # Nacional desde chatbot casual
    ("quiero ver todos los resultados", "nacional"),
    ("muéstrame todos los candidatos con sus votos", "nacional"),
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
