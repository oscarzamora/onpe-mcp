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
    # Geo con "del" y prepositiones
    ("votos del departamento de Moquegua", "geo_domestic"),
    ("resultados electorales del departamento Cusco", "geo_domestic"),
    ("elecciones en la region Junin", "geo_domestic"),
    ("resultados en la provincia Piura", "geo_domestic"),
    # Candidatos con typos
    ("cuantos votos saco Foresyth en Lima", "candidate"),
    ("cuantos votos obtuvo urresti en lima", "candidate"),
    ("votos de sanchez roberto en arequipa", "candidate"),
    # Multi-candidato con geo y sin geo
    ("comparar Nieto y Aliaga en Tacna", "multi_candidate"),
    ("diferencia de votos Lopez Aliaga y Forsyth", "multi_candidate"),
    ("Keiko vs Aliaga en Piura", "multi_candidate"),
    # Consultas extranjero directas
    ("resultados en Tokio", "geo"),
    ("votos peruanos en Frankfurt", "geo"),
    ("cuantos votos en Buenos Aires", "ambiguous"),  # existe en Perú y Argentina
    # Legislativo — el intent devuelto para queries con lugar es legislative_top_candidate
    ("quien son los senadores en Puno", "legislative_top_candidate"),
    ("diputados de Lima", "legislative_top_candidate"),
    # Nacional explícito
    ("ranking de todos los candidatos a nivel del pais", "nacional"),
    ("cuantos votos validos se emitieron en el pais", "nacional"),
    # Candidato con numeros grandes: evitar el número de 6 dígitos que detecta como mesa
    ("Aliaga cuantos votos llevo en Lima", "candidate"),
    # Frases coloquiales con nombre primero
    ("Fujimori cuantos lleva en Arequipa", "candidate"),
    # Frases con typo leve
    ("cuantos votos obtubo Aliaga en Piura", "candidate"),
]
ok_count = sum(run(q, e) for q, e in tests)
print(f"\n{ok_count}/{len(tests)} PASS  {len(tests)-ok_count}/{len(tests)} FAIL")
