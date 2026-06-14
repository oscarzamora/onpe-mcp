"""Cycle 27 stress tests — 20 queries covering:
- Tildes raras (Huánuco, Apurímac, Áncash)
- Nombres largos (4+ palabras)
- Negación mid-sentence ("no X sino Y")
- Consultas de partido (no candidato)
- Rangos de votos ("más de X votos")
- Multi-candidato 3+
- Geo con preposición rara ("hacia Loreto")
- Queries muy cortas sin verbo
- Ruido adicional (coloquial)
"""
import io, logging, sys

if __name__ == '__main__':  # encoding fix only for direct run, not pytest
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
logging.disable(logging.CRITICAL)

from onpe_mcp.server import onpe_chat

TESTS = [
    # Tildes raras
    ("resultados en Huánuco", "geo_domestic"),
    ("top 3 en Apurímac", "geo_domestic"),
    ("cuantos votos obtuvo Aliaga en Áncash", "candidate"),
    # Nombres muy largos
    ("cuantos votos tuvo Fernando Antonio Ugarte Pinto", "candidate"),
    ("resultados de Marco Antonio Tello Ruiz en Cusco", "candidate"),
    # Partido / agrupación
    ("cuantos votos saco Fuerza Popular", "candidate"),  # tratado como candidato/partido
    ("resultados del partido morado", "candidate"),  # no es candidato conocido
    # Rangos/umbrales
    ("candidatos con mas de 50000 votos", "nacional"),
    ("quienes superaron los 100000 votos", "nacional"),
    # Multi-candidato 3+
    ("votos de Aliaga Sagasti y Lescano", "multi_candidate"),
    ("compara a Keiko Aliaga y Hernando de Soto", "multi_candidate"),
    # Geo preposición rara
    ("resultados hacia Loreto", "geo_domestic"),
    ("votos para Tacna", "geo_domestic"),
    # Queries cortas
    ("Huánuco votos", "geo_domestic"),
    ("Arequipa resultados", "geo_domestic"),
    # Negación mid-sentence
    ("no Keiko sino Aliaga en Puno", "candidate"),
    # Ruido coloquial extra
    ("oye como le fue a Sagasti en Lima bro", "candidate"),
    ("pues dime cuantos votos tuvo Urresti ahi en Lima pues", "candidate"),
    # Geo extranjero con tilde
    ("top 5 en Québec", "unknown"),  # Québec no está en el catálogo → unknown es correcto
    ("resultados para peruanos en Tokío", "geo"),
]


def run():
    passed = 0
    failed = 0
    for query, expected in TESTS:
        r = onpe_chat(query)
        d = r.get("data") or {}
        intent = d.get("intent", "ERR")
        ok = intent == expected
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
            print(f"FAIL exp={expected:<20} got={intent:<20} | {query}")
        else:
            passed += 1
            print(f"PASS exp={expected:<20} got={intent:<20} | {query}")
    print(f"\n{passed}/{len(TESTS)} PASS  {failed}/{len(TESTS)} FAIL")


if __name__ == "__main__":
    run()
