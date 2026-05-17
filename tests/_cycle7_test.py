import sys, io, logging
if __name__ == '__main__':  # encoding fix only for direct run, not pytest
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
logging.disable(logging.CRITICAL)
from onpe_mcp.server import onpe_chat

tests = [
    # Regresiones clave
    ("Aliaga frente a Cerron en Puno", "multi_candidate"),
    ("Vizcarra contra Acuna en Ica", "multi_candidate"),
    ("nulos en lima", "geo_domestic"),
    ("viciados en Puno", "geo_domestic"),
    ("top 20 en Peru", "nacional"),
    # Nuevas: variantes de candidatos con tildes y ortografía mezclada
    ("cuantos votos obtuvo keiko fujimori en Lima", "candidate"),
    ("resultados de Rafael Lopez Aliaga en Arequipa", "candidate"),
    ("cuanto saco Aliaga en Ucayali", "candidate"),
    ("votos de Fujimori en Puno", "candidate"),
    # Nuevas: geo extranjero con variantes
    ("cuantos peruanos votaron en Francia", "geo"),
    ("resultados electorales en Suiza", "geo"),
    ("votos peruanos en Nueva Zelanda", "geo"),
    # Nuevas: distritos y provincias específicas
    ("top 3 en San Isidro", "geo_domestic"),
    ("resultados en Barranco", "geo_domestic"),
    ("top 5 en La Molina", "geo_domestic"),
    # Legislativo con variantes
    ("top 3 senadores para Arequipa", "legislative_top_candidate"),
    ("diputados mas votados en Cusco", "legislative_top_candidate"),
    # Nacional variantes nuevas
    ("los 10 primeros candidatos", "nacional"),
    ("candidato con mas votos en todo peru", "nacional"),
    # Mesa con prefijo
    ("informacion de la mesa 900100", "mesa"),
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
