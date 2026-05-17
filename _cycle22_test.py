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
        ans = str(d.get("answer", "no-ans") if d else "no data")[:72]
        print(f"FAIL exp={exp:<26} got={intent:<26} | {q[:58]}")
        print(f"   {ans}")
    else:
        print(f"PASS exp={exp:<26} got={intent:<26} | {q[:58]}")
    return ok

tests = [
    # Candidato con frases "fue a la" / "llegó a la" primera/segunda vuelta
    ("Aliaga fue a la segunda vuelta cuantos votos saco", "candidate"),
    ("Keiko llegó a la segunda vuelta cuantos obtuvo en Lima", "candidate"),
    # Geo con 2-3 palabras
    ("resultados en San Juan de Lurigancho", "geo_domestic"),
    ("votos en Villa Maria del Triunfo", "geo_domestic"),
    ("resultados en La Libertad", "geo_domestic"),
    # Frases con "de" ambiguamente geo
    ("resultados de Ica", "geo_domestic"),  # word-boundary fix: "ica" no es substring de "Ricardo"
    ("resultados de Pasco", "geo_domestic"),
    ("resultados de Tumbes", "geo_domestic"),
    # Candidatos con acento en nombre
    ("cuantos votos tuvo Gonzáles en Puno", "candidate"),
    ("votos de Gálvez en Lima", "candidate"),
    # Multi-candidato con "o" alternativo
    ("Keiko o Aliaga quien gano en Cuzco", "multi_candidate"),
    ("Forsyth o Nieto quien tuvo mas votos", "multi_candidate"),
    # Legislativo variantes
    ("quiero saber sobre los congresistas de Loreto", "legislative_top_candidate"),
    # Nacional con porcientos
    ("qué porcentaje de votos tuvo cada candidato", "nacional"),
    ("distribución de votos entre candidatos", "nacional"),
    # Mesa con texto extra
    ("necesito ver la mesa 900101 por favor", "mesa"),
    # Candidato no encontrado → debe decir candidato
    ("cuantos votos tuvo Perez Mamani en Puno", "candidate"),
    # Geo con tildes
    ("cuantos votos en Junín", "geo_domestic"),
    ("resultados en Áncash por favor", "geo_domestic"),
    # Ambiguo: solo geo word → geo
    ("Lima", "geo_domestic"),
]
ok_count = sum(run(q, e) for q, e in tests)
print(f"\n{ok_count}/{len(tests)} PASS  {len(tests)-ok_count}/{len(tests)} FAIL")
