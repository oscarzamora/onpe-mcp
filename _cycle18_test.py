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
    # Typos deliberados
    ("cuantos votos obtuvo Kiko en lima",  "candidate"),   # Kiko ~ Keiko
    ("Aliaga Rafaell cuantos votos",       "candidate"),
    ("Forsyht en Arequipa",                "candidate"),   # typo Forsyht
    # Preguntas de análisis más largas
    ("cuál fue el resultado de Rafael López Aliaga en la primera vuelta a nivel nacional", "candidate"),
    ("quiero comparar los votos de Keiko y Forsyth en Ucayali", "multi_candidate"),
    ("dame la diferencia de votos entre Lopez Aliaga y Nieto en Loreto", "multi_candidate"),
    # Preguntas con años
    ("resultados electorales 2026 en Lima", "geo_domestic"),
    ("elecciones 2026 Arequipa", "geo_domestic"),
    # Geo doméstico variantes complejas
    ("resultados en San Martin de Porres Lima", "geo_domestic"),
    ("votos en el distrito de Miraflores", "geo_domestic"),
    # Preguntas retóricas con "si"
    ("si Keiko sacó más votos en Lima que en Cusco cuanto fue cada uno", "candidate"),
    # Preguntas sobre participación (no candidatos)
    ("cuántos peruanos votaron en total", "nacional"),
    ("cuánta fue la participación electoral", "nacional"),
    # Extranjero variante: nombre de ciudad ambiguo
    ("resultados en Valencia", "geo"),      # Valencia, España primero en catálogo extranjero
    ("resultados en Santiago", "geo"),      # Santiago de Chile primero en catálogo extranjero
    # Candidatos con titulo honorífico
    ("el señor Forsyth en Lima cuantos votos saco", "candidate"),
    ("la señora Keiko Fujimori en Puno", "candidate"),
    # Multi-candidato con 3
    ("Keiko Forsyth y Aliaga en Lima quien saco mas", "multi_candidate"),
    # Mesa con palabras alrededor
    ("qué resultados tiene la mesa numero 900100", "mesa"),
    ("info de la mesa 900100 por favor", "mesa"),
]
ok_count = sum(run(q, e) for q, e in tests)
print(f"\n{ok_count}/{len(tests)} PASS  {len(tests)-ok_count}/{len(tests)} FAIL")
