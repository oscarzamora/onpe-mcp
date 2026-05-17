import sys, io, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
logging.disable(logging.CRITICAL)
from onpe_mcp.server import onpe_chat

tests = [
    # Geo con ruido verbal
    ("por favor, dame los resultados de Ayacucho", "geo_domestic"),
    ("oye cuanto fue en Tacna?", "geo_domestic"),
    ("me puedes decir como quedó en Ucayali", "geo_domestic"),
    # Candidato con ruido verbal
    ("necesito saber cuantos votos saco Aliaga en la primera vuelta", "candidate"),
    ("dime los votos de Keiko en Piura por favor", "candidate"),
    # Multi-candidato con ruido
    ("a ver, Keiko y Aliaga en Tacna cuantos votos sacaron", "multi_candidate"),
    ("dime quién saco mas entre Nieto y Forsyth en Loreto", "multi_candidate"),
    ("el resultado de Keiko comparado con el de Aliaga en Arequipa", "multi_candidate"),
    # Extranjero
    ("cuántos peruanos votaron en Japón", "geo"),
    ("resultados electorales en Francia", "geo"),
    ("top 5 en Canadá", "geo"),
    # Nacional
    ("cuántos candidatos se presentaron", "nacional"),
    ("dame todos los votos", "nacional"),
    # Legislativo
    ("cuántos diputados corresponden a Lima", "legislative_top_candidate"),
    ("escaños para Arequipa", "legislative_top_candidate"),
    # Mesa
    ("consulta la mesa 123456", "ONPE_API_ERROR"),  # mesa no existe → error API
    ("qué pasó en la mesa 900100", "mesa"),
    # Ambiguo / unknown
    ("¿quién ganó la elección?", "unknown"),  # query not clear on level
    ("hola", "unknown"),
    # Candidato con alias
    ("castillo votos en Puno", "candidate"),  # castillo → sombrero → Sánchez
]
ok=0; fail=0
for q, exp in tests:
    r = onpe_chat(q)
    d = r.get("data") or {}
    intent = d.get("intent", "ERR") if d else r.get("errors", [{}])[0].get("code", "ERR")
    ok += int(intent == exp)
    fail += int(intent != exp)
    status = "PASS" if intent == exp else "FAIL"
    ans = str(d.get("answer", "?"))[:70]
    print(f"{status} exp={exp:<26} got={intent:<26} | {q[:55]}")
    if "FAIL" in status:
        print(f"   ANS: {ans}")
print(f"\n{ok}/20 PASS  {fail}/20 FAIL")
