import sys, io, logging
if __name__ == '__main__':  # encoding fix only for direct run, not pytest
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
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
    # Primera/segunda vuelta CON geo → candidate o geo_domestic
    ("como quedó Aliaga en la primera vuelta en Cajamarca", "candidate"),
    ("resultados primera vuelta en Cajamarca", "geo_domestic"),
    ("resultados de segunda vuelta en Piura", "geo_domestic"),
    # Geo con nombres largos de provincias
    ("resultados en Huánuco", "geo_domestic"),
    ("resultados en Áncash", "geo_domestic"),
    ("resultados en Apurímac", "geo_domestic"),
    ("votos en Madre de Dios", "geo_domestic"),
    # Candidatos con títulos honoríficos
    ("cuantos votos saco el Dr Forsyth en Lima", "candidate"),
    ("cuantos votos tuvo el Lic. Aliaga en Arequipa", "candidate"),
    ("el Ing. Urresti en Puno cuantos votos", "candidate"),
    # Candidatos con apellido compuesto
    ("cuantos votos recibio Lopez Aliaga en Moquegua", "candidate"),
    ("votos de Roberto Sanchez Palomino en Lima", "candidate"),
    ("cuantos obtuvo Rafael Lopez Aliaga en Ica", "candidate"),
    # Multi-cand con "ambos" / "los dos" / "tanto X como Y"
    ("tanto Keiko como Aliaga en Lima cuantos votos", "multi_candidate"),
    # Geo extranjero con pais explicito
    ("resultados para peruanos en Italia", "geo"),
    ("cuantos peruanos votaron en Alemania", "geo"),
    # Nacional con frases negativas
    ("que candidato NO gano las elecciones generales", "nacional"),
    # Mesa explícita — sistema detecta mesa correctamente
    ("datos de la mesa 123456", "mesa"),
    ("resultados mesa 050101", "mesa"),
    # Ambiguo que no puede resolverse → unknown (consulta demasiado vaga)
    ("algo sobre la eleccion", "unknown"),
]
ok_count = sum(run(q, e) for q, e in tests)
print(f"\n{ok_count}/{len(tests)} PASS  {len(tests)-ok_count}/{len(tests)} FAIL")
