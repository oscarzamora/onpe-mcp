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
    ans = str(d.get("answer", r.get("errors", "?")) if d else "no data")[:70]
    print(f"{'PASS' if ok else 'FAIL'} exp={exp:<26} got={intent:<26} | {q[:55]}")
    if not ok:
        print(f"   {ans}")
    return ok

tests = [
    # Variantes sin tildes
    ("cuantos votos saco Keiko en Junin", "candidate"),
    ("resultados en Huanuco", "geo_domestic"),
    ("Aliaga en Huancavelica", "candidate"),
    # Mayúsculas/minúsculas
    ("KEIKO EN LIMA CUANTOS VOTOS", "candidate"),
    ("RESULTADOS EN AREQUIPA", "geo_domestic"),
    # Queries con puntuación
    ("¿cuántos votos tuvo Forsyth?", "candidate"),
    ("Forsyth, cuántos votos?", "candidate"),
    # Multi-candidato con puntuación
    ("Keiko: ¿cuántos votos? y Aliaga: ¿cuántos votos?", "multi_candidate"),
    # Geo con artículo
    ("los resultados de la región Cusco", "geo_domestic"),
    ("en el departamento de Madre de Dios", "geo_domestic"),
    # Candidato con "el" / "la"
    ("cuantos votos saco el candidato Nieto en Lima", "candidate"),
    ("la candidata Fujimori en Puno", "candidate"),
    # Frases ambiguas moderadas
    ("Lima resultados", "geo_domestic"),
    ("Puno votos", "geo_domestic"),
    # Nacional con "total"
    ("el total de votos por candidato", "nacional"),
    ("resultados totales del pais", "nacional"),
    # Extranjero específico
    ("top 3 en Argentina", "geo"),
    ("resultados peruanos en Estados Unidos", "geo"),
    # Legislativo variantes
    ("cuántos diputados tiene Puno", "legislative_top_candidate"),
    ("cuantos senadores hay para Lima", "legislative_top_candidate"),
]
ok_count = sum(run(q, e) for q, e in tests)
print(f"\n{ok_count}/{len(tests)} PASS  {len(tests)-ok_count}/{len(tests)} FAIL")
