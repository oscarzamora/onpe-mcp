import sys, io, logging
if __name__ == '__main__':  # encoding fix only for direct run, not pytest
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
logging.disable(logging.CRITICAL)
from onpe_mcp.server import onpe_chat

tests = [
    # Regresiones
    ("top 3 de candidatos en Suecia", "geo"),
    ("top 5 en Junin", "geo_domestic"),
    ("Lopez Aliaga y Fujimori cuantos votos sacaron", "multi_candidate"),
    ("cuantos votos saco Keiko a nivel nacional", "candidate"),
    # Multi-candidato: 3 candidatos (parcialmente soportado)
    ("Keiko, Aliaga y Nieto cuantos votos sacaron", "multi_candidate"),
    # Geo con texto extra
    ("cuales son los resultados en Puno", "geo_domestic"),
    ("como van las elecciones en Arequipa", "geo_domestic"),
    ("quien va ganando en Tacna", "geo_domestic"),
    # Candidato con apellido compuesto
    ("cuantos votos tiene Lopez Aliaga en Loreto", "candidate"),
    ("resultados de Keiko Fujimori en Cusco", "candidate"),
    # Noisy queries
    ("hola quiero saber los votos de Aliaga", "candidate"),
    ("por favor dame los resultados de Keiko en Lima", "candidate"),
    ("me gustaria saber cuantos votos tuvo Acuna", "candidate"),
    # Preguntas con acentos completos
    ("cuántos votos obtuvo López Aliaga en Loreto", "candidate"),
    ("quién ganó en Arequipa", "geo_domestic"),
    # Mesa con formato alternativo
    ("9 0 0 1 0 0", "unknown"),  # digits with spaces → can't reliably parse as mesa
    ("la mesa tiene codigo 900100", "mesa"),
    # Extranjero con países no estándar
    ("votos en Ecuador", "geo"),
    ("resultados electorales Bolivia", "geo"),
    # Nacional edge
    ("dame el top 5", "nacional"),
    ("muéstrame los resultados generales", "nacional"),
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
