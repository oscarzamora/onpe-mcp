"""Cycle 33 stress tests — 20 queries:
- Queries con errores graves de ortografía
- Candidato con partido mencionado
- Queries de posición geográfica alternativa ("en la selva", "en la sierra")
- Consultas mixtas candidato + mesa
- Queries de historial ("en 2021")
- Geo extranjero: continentes
- Queries de comparación "más que"
- Candidato con "la señora" / "el señor"
- Preguntas sobre inscripción de candidatos
- Queries ultra cortas con intención clara
"""
import io, logging, sys

if __name__ == '__main__':  # encoding fix only for direct run, not pytest
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
logging.disable(logging.CRITICAL)

from onpe_mcp.server import onpe_chat

TESTS = [
    # Errores graves de ortografía
    ("cuantos botos tubo aliaga", "candidate"),  # botos=votos, tubo=tuvo
    ("resultados de la elecsion en puno", "geo_domestic"),
    # Candidato con partido mencionado
    ("cuantos votos saco Aliaga de Renovacion Popular en Lima", "candidate"),
    # Región geográfica natural
    ("resultados en la sierra peruana", "nacional"),
    ("resultados en la selva", "nacional"),
    # Mesa con candidato en misma pregunta → mesa tiene prioridad
    ("en la mesa 123456 cuantos votos tuvo Aliaga", "mesa"),
    # Elecciones 2021 con geo → year guard → unknown (solo datos 2026)
    ("resultados de las elecciones 2021 en Puno", "unknown"),
    # Geo extranjero: continentes — no están en catálogo de ciudades
    ("resultados de peruanos en Europa", "unknown"),
    ("top 5 de peruanos en Asia", "geo_domestic"),  # "Asia" es distrito en Lima
    # Comparación "más que"
    ("Aliaga tuvo mas votos que Sagasti", "multi_candidate"),
    # "mas que Castillo en Lima" — multi-candidato (Keiko vs Castillo)
    ("Keiko saco mas que Castillo en Lima", "multi_candidate"),
    # Candidato con "la señora" / "el señor"
    ("cuantos votos tuvo la señora Keiko", "candidate"),
    ("resultados del señor López Aliaga en Arequipa", "candidate"),
    # Preguntas sobre inscripción
    ("cuantos candidatos se inscribieron", "nacional"),
    # Ultra cortas con intención
    ("Aliaga Puno", "geo_domestic"),  # bare name+geo → geo_domestic
    ("Keiko Lima", "geo_domestic"),   # bare name+geo → geo_domestic
    # Preguntas de porcentaje nacional
    ("que porcentaje saco cada candidato", "nacional"),
    # Geo con "zona"
    ("resultados en la zona norte de Lima", "geo_domestic"),
    # Candidato + número (no mesa)
    ("cuantos votos tuvo Aliaga en el puesto 1", "candidate"),
    # Geo ambiguo país/ciudad: Chile
    ("resultados de peruanos en Chile", "geo"),
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
