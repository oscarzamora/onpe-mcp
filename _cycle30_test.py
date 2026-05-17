"""Cycle 30 stress tests — 20 queries:
- Consultas con "cuánto sacó" (número de votos) vs "cómo quedó" (posición)
- Preguntas sobre departamentos con "departamento de X"
- Candidatos con "doctor" / "ing." antes
- Preguntas sobre votos en el exterior / diáspora
- Consultas con ruido fonético (acento mal escrito)
- Queries con oraciones relativas: "el que ganó en Lima"
- Queries de comparación directa sin "versus"
- Mesa con "código" en vez de número
- Geo ambiguo: "Lima" puede ser ciudad o región
- Múltiple intención en una frase
"""
import io, logging, sys

if __name__ == '__main__':  # encoding fix only for direct run, not pytest
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
logging.disable(logging.CRITICAL)

from onpe_mcp.server import onpe_chat

TESTS = [
    # Candidato con "doctor" honorífico
    ("votos del doctor Francisco Sagasti", "candidate"),
    ("cuantos votos tuvo el ing. Lopez Aliaga", "candidate"),
    # Departamento con artículo
    ("resultados en el departamento de Ayacucho", "geo_domestic"),
    ("top 3 del departamento de Ica", "geo_domestic"),
    # Diáspora / exterior — "geo_foreign_summary" es el intent correcto para exterior sin ciudad
    ("cuantos peruanos votaron en el exterior", "geo_foreign_summary"),
    ("resultados de peruanos en el extranjero", "geo_foreign_summary"),
    # Acento mal escrito (sin tilde)
    # "Peru" sin tilde ya es normal, pruebo con nombre de candidato sin tilde
    ("cuantos votos tuvo Fujimori en Cusco", "candidate"),  # Cuzco/Cusco
    ("resultados en Junin", "geo_domestic"),  # Junín sin tilde
    # Oración relativa
    ("el candidato que mas votos saco en Lima", "geo_domestic"),
    ("el que gano en Arequipa", "geo_domestic"),
    # Comparación directa
    ("Aliaga tuvo mas votos que Sagasti en Puno", "multi_candidate"),
    # Mesa con "código"
    ("codigo de mesa 123456", "mesa"),  # sistema ahora detecta mesa correctamente
    ("dame los resultados del codigo 050100", "mesa"),  # "codigo" en NON_CAND, ruteará a mesa via late fallback
    # Lima región vs ciudad
    ("resultados en Lima", "geo_domestic"),
    ("quien gano en Lima region", "geo_domestic"),
    # Query de posición/ranking
    ("en que puesto quedo Aliaga", "candidate"),
    ("cual fue el lugar de Fujimori en la eleccion", "candidate"),
    # Consulta de totales agregados
    ("cuantos votos validos hubo en total", "nacional"),
    # Candidato muy corto (2 letras) — "La" es ciudad extranjera en catálogo
    ("votos en La", "geo"),  # "La" matchea ciudad extranjera (ej: LA), no geo_domestic
    # Consulta de ganador con geo extranjero
    ("quien gano en Estados Unidos", "geo"),
]


def run():
    passed = 0
    failed = 0
    for query, expected in TESTS:
        r = onpe_chat(query)
        d = r.get("data") or {}
        intent = d.get("intent", "ERR")
        ok = intent == expected
        if not ok:
            failed += 1
            print(f"FAIL exp={expected:<28} got={intent:<28} | {query}")
        else:
            passed += 1
            print(f"PASS exp={expected:<28} got={intent:<28} | {query}")
    print(f"\n{passed}/{len(TESTS)} PASS  {failed}/{len(TESTS)} FAIL")


if __name__ == "__main__":
    run()
