import sys, io, logging
if __name__ == '__main__':  # encoding fix only for direct run, not pytest
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
logging.disable(logging.CRITICAL)
from onpe_mcp.server import onpe_chat

tests = [
    # Regresiones clave de todos los ciclos
    ("cuantos votos saco Keiko a nivel nacional", "candidate"),
    ("top 3 de candidatos en Suecia", "geo"),
    ("resultados en Buenos Aires", "ambiguous"),
    ("cuantos votos saco Pedro Castillo", "candidate"),  # 2021, should return not-found with hint
    # Queries coloquiales / chat natural
    ("oye cuanto saco Aliaga en Lima?", "candidate"),
    ("sabes cuantos votos tuvo Keiko en Piura", "candidate"),
    ("me dices los resultados de Nieto en Arequipa?", "candidate"),
    ("como le fue a Forsyth en la primera vuelta", "candidate"),
    ("Fujimori Lima resultados primera vuelta", "candidate"),
    # Multi-candidato con ruido de chat
    ("quien saco mas Keiko o Aliaga?", "multi_candidate"),
    ("entre Keiko y Aliaga quien gano en Lima?", "multi_candidate"),
    ("cuál es la diferencia entre Aliaga y Nieto?", "multi_candidate"),
    # Geo con nombre largo
    ("resultados en Padre Abad", "geo_domestic"),
    ("top 5 en San Martin de Porres", "geo_domestic"),
    ("votos en San Juan de Miraflores", "geo_domestic"),
    # Geo foreign complejo
    ("cuantos votos en el exterior", "geo_foreign_summary"),
    ("resultados en el extranjero", "geo_foreign_summary"),
    # Nacional
    ("muéstrame el top 10 de candidatos", "nacional"),
    # Incompleta
    ("resultados", "unknown"),
    ("mesa", "unknown"),
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
