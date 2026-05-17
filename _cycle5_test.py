import sys, io, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
logging.disable(logging.CRITICAL)
from onpe_mcp.server import onpe_chat

tests = [
    ("cuantos votos saco rafael lopez aliaga","candidate"),
    ("keiko cuantos votos tiene","candidate"),
    ("vizcarrra en arequipa","candidate"),
    ("acuna piura votos","candidate"),
    ("de las mesas que arrancan en 900000 quien tuvo mas votos","ERR"),
    ("votos","unknown"),
    ("en Lima","geo_domestic"),
    ("top","unknown"),
    ("Keiko Fujimori o Lopez Aliaga quien saco mas votos","multi_candidate"),
    ("Forsyth frente a Acuna en Loreto","multi_candidate"),
    ("resultados en Miraflores","geo_domestic"),
    ("votos en Callao","geo_domestic"),
    ("top 5 en Madre de Dios","geo_domestic"),
    ("quien lidera las encuestas 2026","unknown"),
    ("podio electoral Peru","nacional"),
    ("cuantos escanos gano Keiko en Lima","legislative_top_candidate"),
    ("senadores elegidos Arequipa","legislative_top_candidate"),
    ("resultados Peru en Italia","geo"),
    ("cuantos peruanos votaron en Alemania","geo"),
    ("dame el estado de la mesa numero 900100","mesa"),
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
