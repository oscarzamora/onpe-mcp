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
    # Candidatos con "a" preposición
    ("cuantos votos tuvo a favor Keiko en Lima", "candidate"),
    ("votos a favor de Aliaga en Puno", "candidate"),
    # Geo con "del" y "al"
    ("resultados al norte del pais", "nacional"),  # "al norte" → nacional
    ("resultados al sur de Lima", "geo_domestic"),  # "de Lima" → geo_domestic
    # Candidatos con frase prepositiva
    ("información acerca de los votos de Nieto en Ica", "candidate"),
    ("datos acerca de Forsyth en Arequipa", "candidate"),
    # Multi-candidato con "ni" → muy complejo, devolver candidate no-encontrado
    ("ni Keiko ni Aliaga ganaron en Puno sino quien", "candidate"),
    # Geo extranjero con "la" antes del país
    ("resultados en la Argentina", "geo"),
    ("resultados en el Japón", "geo"),
    # Consultas de participación
    ("cuantos peruanos fueron a votar en total", "nacional"),
    ("cuanta gente voto en Lima", "geo_domestic"),
    # Legislativo con variantes
    ("cuantos escaños tiene la alianza en Lima", "legislative_top_candidate"),
    ("cuantos senadores hay en Tacna", "legislative_top_candidate"),
    # Candidato con "ganó en" patrón
    ("Keiko ganó en Lima cuantos votos fue eso", "candidate"),
    ("cuantos votos fue que saco Aliaga en Puno", "candidate"),
    # Mesa con variantes de texto
    ("quiero ver los resultados de la mesa numero 900101", "mesa"),
    # Geo con "la" antes del nombre
    ("resultados en la region Huanuco", "geo_domestic"),
    ("cuantos votos en la provincia de Ica", "geo_domestic"),
    # "resultados en todas las regiones" → nacional (todas=colectivo, no geo específico)
    ("resultados en todas las regiones", "nacional"),
    # "Aliaga Tacna" bare 2-word → geo_domestic (sistema ruteá Tacna)
    ("Aliaga Tacna", "geo_domestic"),
]
ok_count = sum(run(q, e) for q, e in tests)
print(f"\n{ok_count}/{len(tests)} PASS  {len(tests)-ok_count}/{len(tests)} FAIL")
