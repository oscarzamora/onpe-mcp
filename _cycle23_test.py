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
    # Regresión de ciclos anteriores
    ("cuántos votos obtuvo Rafael López Aliaga en primera vuelta", "candidate"),
    ("cuántos votos obtuvo nieto en arequipa", "candidate"),
    ("cuántos votos obtuvo Rafael López Aliaga y fujimori en iquitos", "multi_candidate"),
    ("top 3 de candidatos en Suecia", "geo"),
    ("resultados en Estocolmo", "geo"),
    ("top 3 en Loreto", "geo_domestic"),
    ("senadores top 10 para Cuzco", "legislative_top_candidate"),
    ("consulta mesa 900100", "mesa"),
    ("cuantos votos obtuvo Lopez Aliaga en puno", "candidate"),
    # Nuevas: frases muy largas con ruido
    ("me gustaría saber si es posible obtener información sobre cuántos votos recibió Forsyth en Lima", "candidate"),
    ("podrías decirme por favor cuántos votos sacó Aliaga en Arequipa durante la primera vuelta", "candidate"),
    # Candidatos con "el señor" / "la señora" 
    ("el señor Urresti cuantos votos saco en Moquegua", "candidate"),
    ("la señora Fujimori cuantos obtuvo en Tacna", "candidate"),
    # Geo muy largas
    ("resultados electorales en el distrito de San Juan de Miraflores Lima", "geo_domestic"),
    # Nacional con variantes
    ("quiero el listado completo de candidatos con sus votos", "nacional"),
    ("ponme el resumen de todos los partidos políticos con sus votos", "nacional"),
    # Multi-candidato con geo extranjero
    ("Keiko y Aliaga cuantos votos en Madrid", "multi_candidate"),
    # Frases con negación / "sino" → demasiado complejo, geo_domestic por Lima
    ("no me digas de Forsyth sino de Aliaga en Lima", "geo_domestic"),
    # Frases mezcladas
    ("en Lima quien gano", "geo_domestic"),
    ("en la seleccion... quiero decir en Loreto quien saco mas votos", "geo_domestic"),
]
ok_count = sum(run(q, e) for q, e in tests)
print(f"\n{ok_count}/{len(tests)} PASS  {len(tests)-ok_count}/{len(tests)} FAIL")
