#!/usr/bin/env python3
"""
benchmark_denorm.py — Compara tiempos de query entre:
  - onpe.db       (modelo OLTP / joins en caliente)
  - onpe_denorm.db (modelo BI denormalizado)

Cubre permutaciones de: mesa exacta, rango de mesas, departamento,
provincia, ubigeo/distrito, nacional, país/ciudad exterior,
comparación 2021 vs 2026, y queries mixtas.
"""
from __future__ import annotations

import sqlite3
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT     = Path(__file__).parent.parent
OLTP_DB  = ROOT / "data" / "onpe.db"
DENORM_DB= ROOT / "data" / "onpe_denorm.db"

RUNS = 5   # repeticiones por query para medir p50

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BenchResult:
    label: str
    category: str
    oltp_ms: float       # mediana de RUNS
    denorm_ms: float
    rows_oltp: int
    rows_denorm: int
    match: bool
    note: str = ""

    @property
    def speedup(self) -> float:
        return self.oltp_ms / self.denorm_ms if self.denorm_ms > 0 else float("inf")

    @property
    def saved_ms(self) -> float:
        return self.oltp_ms - self.denorm_ms


def _run(conn: sqlite3.Connection, sql: str, params=()) -> tuple[float, int]:
    """Returns (median_ms, row_count)."""
    times: list[float] = []
    rows = 0
    for i in range(RUNS):
        t0 = time.perf_counter()
        cur = conn.execute(sql, params)
        rows = len(cur.fetchall())
        times.append((time.perf_counter() - t0) * 1000)
    return statistics.median(times), rows


def bench(
    label: str,
    category: str,
    oltp_conn: sqlite3.Connection,
    denorm_conn: sqlite3.Connection,
    oltp_sql: str,
    denorm_sql: str,
    oltp_params=(),
    denorm_params=(),
    note: str = "",
) -> BenchResult:
    oltp_ms,   oltp_rows   = _run(oltp_conn,   oltp_sql,   oltp_params)
    denorm_ms, denorm_rows = _run(denorm_conn, denorm_sql, denorm_params)
    match = oltp_rows == denorm_rows
    return BenchResult(
        label=label, category=category,
        oltp_ms=round(oltp_ms, 2), denorm_ms=round(denorm_ms, 2),
        rows_oltp=oltp_rows, rows_denorm=denorm_rows,
        match=match, note=note,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Query definitions
# ─────────────────────────────────────────────────────────────────────────────

def build_benchmarks(oltp: sqlite3.Connection, dn: sqlite3.Connection) -> list[BenchResult]:
    results: list[BenchResult] = []
    r = lambda *a, **kw: results.append(bench(*a, oltp_conn=oltp, denorm_conn=dn, **kw))

    # ── MESA — lookup exacto ──────────────────────────────────────────────────
    r(
        "Mesa exacta 1v2026 (votos de 1 mesa)",
        "Mesa lookup",
        oltp_sql="""
            SELECT v.partido_id, ag.nombre, v.votos
            FROM votos v
            JOIN agrupaciones ag ON ag.partido_id = v.partido_id
            WHERE v.codigo_mesa = '054321'
            ORDER BY v.votos DESC
        """,
        denorm_sql="""
            SELECT partido_id, nombre_partido, votos
            FROM fact_votos_mesa
            WHERE election_year=2026 AND vuelta=1 AND codigo_mesa='054321'
            ORDER BY votos DESC
        """,
    )

    r(
        "Mesa exacta 2v2026 (votos de 1 mesa)",
        "Mesa lookup",
        oltp_sql="""
            SELECT v.partido_id, ag.nombre, v.votos
            FROM votos_sv v
            JOIN agrupaciones_sv ag ON ag.partido_id = v.partido_id
            WHERE v.codigo_mesa = '054321'
            ORDER BY v.votos DESC
        """,
        denorm_sql="""
            SELECT partido_id, nombre_partido, votos
            FROM fact_votos_mesa
            WHERE election_year=2026 AND vuelta=2 AND codigo_mesa='054321'
            ORDER BY votos DESC
        """,
    )

    r(
        "Mesa exacta 2v2021 (votos de 1 mesa)",
        "Mesa lookup",
        oltp_sql="""
            SELECT v.partido_id, p.nombre_partido, v.votos
            FROM votos_2021 v
            JOIN partidos_2021 p ON p.partido_id=v.partido_id AND p.vuelta=v.vuelta
            WHERE v.codigo_mesa='054321' AND v.vuelta=2
            ORDER BY v.votos DESC
        """,
        denorm_sql="""
            SELECT partido_id, nombre_partido, votos
            FROM fact_votos_mesa
            WHERE election_year=2021 AND vuelta=2 AND codigo_mesa='054321'
              AND es_especial=0
            ORDER BY votos DESC
        """,
        note="OLTP no incluye blancos/nulos",
    )

    # ── MESA — rango numérico ─────────────────────────────────────────────────
    r(
        "Rango de mesas 1-500 (1v2026, todos los partidos)",
        "Mesa range",
        oltp_sql="""
            SELECT v.codigo_mesa, v.partido_id, v.votos,
                   m.ubigeo, m.estado_acta
            FROM votos v
            JOIN mesas_data m ON m.codigo_mesa = v.codigo_mesa
            WHERE CAST(v.codigo_mesa AS INTEGER) BETWEEN 1 AND 500
            ORDER BY v.codigo_mesa, v.partido_id
        """,
        denorm_sql="""
            SELECT codigo_mesa, partido_id, votos, ubigeo, estado_acta
            FROM fact_votos_mesa
            WHERE election_year=2026 AND vuelta=1
              AND mesa_num BETWEEN 1 AND 500
            ORDER BY mesa_num, partido_id
        """,
        note="OLTP: CAST en vuelo | Denorm: integer B-tree",
    )

    r(
        "Rango de mesas 10000-11000 (1v2026, candidatos)",
        "Mesa range",
        oltp_sql="""
            SELECT v.codigo_mesa, v.partido_id, ag.nombre, v.votos,
                   m.ubigeo, m.estado_acta
            FROM votos v
            JOIN mesas_data m ON m.codigo_mesa = v.codigo_mesa
            JOIN agrupaciones ag ON ag.partido_id = v.partido_id
            WHERE CAST(v.codigo_mesa AS INTEGER) BETWEEN 10000 AND 11000
              AND v.partido_id NOT IN ('80','81','82')
            ORDER BY v.codigo_mesa, v.votos DESC
        """,
        denorm_sql="""
            SELECT codigo_mesa, partido_id, nombre_partido, votos,
                   ubigeo, estado_acta
            FROM fact_votos_mesa
            WHERE election_year=2026 AND vuelta=1
              AND mesa_num BETWEEN 10000 AND 11000
              AND es_especial = 0
            ORDER BY mesa_num, votos DESC
        """,
    )

    r(
        "Rango de mesas 50000-55000 (2v2026)",
        "Mesa range",
        oltp_sql="""
            SELECT v.codigo_mesa, v.partido_id, ag.nombre, v.votos
            FROM votos_sv v
            JOIN agrupaciones_sv ag ON ag.partido_id = v.partido_id
            WHERE CAST(v.codigo_mesa AS INTEGER) BETWEEN 50000 AND 55000
            ORDER BY v.codigo_mesa, v.votos DESC
        """,
        denorm_sql="""
            SELECT codigo_mesa, partido_id, nombre_partido, votos
            FROM fact_votos_mesa
            WHERE election_year=2026 AND vuelta=2
              AND mesa_num BETWEEN 50000 AND 55000
            ORDER BY mesa_num, votos DESC
        """,
    )

    # ── DEPARTAMENTO ──────────────────────────────────────────────────────────
    r(
        "Votos por partido en LIMA (cod_dept=14) — 1v2026",
        "Departamento",
        oltp_sql="""
            SELECT v.partido_id, ag.nombre,
                   SUM(v.votos) AS total_votos
            FROM votos v
            JOIN mesas_data m ON m.codigo_mesa = v.codigo_mesa
            JOIN agrupaciones ag ON ag.partido_id = v.partido_id
            WHERE SUBSTR('000000'||m.ubigeo,-6,2) = '14'
              AND v.partido_id NOT IN ('80','81','82')
            GROUP BY v.partido_id, ag.nombre
            ORDER BY total_votos DESC
        """,
        denorm_sql="""
            SELECT partido_id, nombre_partido, votos
            FROM fact_votos_departamento
            WHERE election_year=2026 AND vuelta=1
              AND cod_departamento = '14' AND es_especial=0
            ORDER BY votos DESC
        """,
    )

    r(
        "Votos por partido en LIMA (cod_dept=14) — 2v2026",
        "Departamento",
        oltp_sql="""
            SELECT v.partido_id, ag.nombre,
                   SUM(v.votos) AS total_votos
            FROM votos_sv v
            JOIN mesas_sv m ON m.codigo_mesa = v.codigo_mesa
            JOIN agrupaciones_sv ag ON ag.partido_id = v.partido_id
            WHERE SUBSTR(m.id_ubigeo,1,2) = '14'
              AND v.partido_id NOT IN ('80','81','82')
            GROUP BY v.partido_id, ag.nombre
            ORDER BY total_votos DESC
        """,
        denorm_sql="""
            SELECT partido_id, nombre_partido, votos
            FROM fact_votos_departamento
            WHERE election_year=2026 AND vuelta=2
              AND cod_departamento = '14' AND es_especial=0
            ORDER BY votos DESC
        """,
    )

    r(
        "Votos por partido en AREQUIPA (dept=04) — 2v2021",
        "Departamento",
        oltp_sql="""
            SELECT v.partido_id, p.nombre_partido,
                   SUM(v.votos) AS total_votos
            FROM votos_2021 v
            JOIN mesas_2021 m ON m.codigo_mesa=v.codigo_mesa AND m.vuelta=v.vuelta
            JOIN partidos_2021 p ON p.partido_id=v.partido_id AND p.vuelta=v.vuelta
            WHERE UPPER(m.departamento) = 'AREQUIPA' AND v.vuelta=2
            GROUP BY v.partido_id, p.nombre_partido
            ORDER BY total_votos DESC
        """,
        denorm_sql="""
            SELECT partido_id, nombre_partido, votos
            FROM fact_votos_departamento
            WHERE election_year=2021 AND vuelta=2
              AND departamento = 'AREQUIPA' AND es_especial=0
            ORDER BY votos DESC
        """,
    )

    r(
        "Ranking de TODOS los departamentos 1v2026 — partido 14",
        "Departamento",
        oltp_sql="""
            SELECT SUBSTR('000000'||m.ubigeo,-6,2) AS cod_dept,
                   SUM(v.votos) AS votos
            FROM votos v
            JOIN mesas_data m ON m.codigo_mesa = v.codigo_mesa
            WHERE v.partido_id = '14'
            GROUP BY cod_dept
            ORDER BY votos DESC
        """,
        denorm_sql="""
            SELECT cod_departamento, votos
            FROM fact_votos_departamento
            WHERE election_year=2026 AND vuelta=1 AND partido_id='14'
            ORDER BY votos DESC
        """,
    )

    # ── PROVINCIA ────────────────────────────────────────────────────────────
    r(
        "Votos por partido en Lima Metropolitana (prov=1401) — 1v2026",
        "Provincia",
        oltp_sql="""
            SELECT v.partido_id, ag.nombre,
                   SUM(v.votos) AS total_votos
            FROM votos v
            JOIN mesas_data m ON m.codigo_mesa = v.codigo_mesa
            JOIN agrupaciones ag ON ag.partido_id = v.partido_id
            WHERE SUBSTR('000000'||m.ubigeo,-6,4) = '1401'
              AND v.partido_id NOT IN ('80','81','82')
            GROUP BY v.partido_id, ag.nombre
            ORDER BY total_votos DESC
        """,
        denorm_sql="""
            SELECT partido_id, nombre_partido, votos
            FROM fact_votos_provincia
            WHERE election_year=2026 AND vuelta=1
              AND cod_provincia='1401' AND es_especial=0
            ORDER BY votos DESC
        """,
    )

    r(
        "Ranking TODAS las provincias de LIMA 1v2026 — partido 8",
        "Provincia",
        oltp_sql="""
            SELECT SUBSTR('000000'||m.ubigeo,-6,4) AS cod_prov,
                   SUM(v.votos) AS votos
            FROM votos v
            JOIN mesas_data m ON m.codigo_mesa = v.codigo_mesa
            WHERE v.partido_id='8'
              AND SUBSTR('000000'||m.ubigeo,-6,2)='14'
            GROUP BY cod_prov
            ORDER BY votos DESC
        """,
        denorm_sql="""
            SELECT cod_provincia, votos
            FROM fact_votos_provincia
            WHERE election_year=2026 AND vuelta=1
              AND partido_id='8' AND SUBSTR(cod_provincia,1,2)='14'
            ORDER BY votos DESC
        """,
    )

    # ── UBIGEO / DISTRITO ────────────────────────────────────────────────────
    r(
        "Votos por partido en ubigeo 140137 (San Juan de Lurigancho) — 1v2026",
        "Ubigeo",
        oltp_sql="""
            SELECT v.partido_id, ag.nombre, SUM(v.votos) AS votos
            FROM votos v
            JOIN mesas_data m ON m.codigo_mesa = v.codigo_mesa
            JOIN agrupaciones ag ON ag.partido_id = v.partido_id
            WHERE SUBSTR('000000'||m.ubigeo,-6) = '140137'
              AND v.partido_id NOT IN ('80','81','82')
            GROUP BY v.partido_id
            ORDER BY votos DESC
        """,
        denorm_sql="""
            SELECT partido_id, nombre_partido, votos
            FROM fact_votos_ubigeo
            WHERE election_year=2026 AND vuelta=1
              AND ubigeo='140137' AND es_especial=0
            ORDER BY votos DESC
        """,
    )

    r(
        "Votos por partido en ubigeo 140137 (SJL) — 2v2026",
        "Ubigeo",
        oltp_sql="""
            SELECT v.partido_id, ag.nombre, SUM(v.votos) AS votos
            FROM votos_sv v
            JOIN mesas_sv m ON m.codigo_mesa = v.codigo_mesa
            JOIN agrupaciones_sv ag ON ag.partido_id = v.partido_id
            WHERE m.id_ubigeo = '140137'
              AND v.partido_id NOT IN ('80','81','82')
            GROUP BY v.partido_id
            ORDER BY votos DESC
        """,
        denorm_sql="""
            SELECT partido_id, nombre_partido, votos
            FROM fact_votos_ubigeo
            WHERE election_year=2026 AND vuelta=2
              AND ubigeo='140137' AND es_especial=0
            ORDER BY votos DESC
        """,
    )

    r(
        "Cobertura de actas por ubigeo en Lima — 2v2026",
        "Ubigeo",
        oltp_sql="""
            SELECT SUBSTR(m.id_ubigeo,1,6) AS ubigeo,
                   COUNT(*) as total,
                   SUM(CASE WHEN m.codigo_estado_acta='C' THEN 1 ELSE 0 END) as cont
            FROM mesas_sv m
            WHERE SUBSTR(m.id_ubigeo,1,2)='14'
            GROUP BY ubigeo
            ORDER BY ubigeo
        """,
        denorm_sql="""
            SELECT ubigeo, total_mesas, mesas_contabilizadas
            FROM fact_votos_ubigeo
            WHERE election_year=2026 AND vuelta=2
              AND cod_departamento='14' AND partido_id='8'
            ORDER BY ubigeo
        """,
        note="Denorm incluye partido_id como key; OLTP agrega solo por ubigeo",
    )

    # ── NACIONAL ──────────────────────────────────────────────────────────────
    r(
        "Resultados nacionales 1v2026 (todos los candidatos)",
        "Nacional",
        oltp_sql="""
            SELECT v.partido_id, ag.nombre,
                   SUM(v.votos) AS total_votos,
                   ROUND(100.0*SUM(v.votos)/SUM(SUM(v.votos)) OVER(), 4) AS pct
            FROM votos v
            JOIN agrupaciones ag ON ag.partido_id = v.partido_id
            WHERE v.partido_id NOT IN ('80','81','82')
            GROUP BY v.partido_id, ag.nombre
            ORDER BY total_votos DESC
        """,
        denorm_sql="""
            SELECT partido_id, nombre_partido, votos, pct_votos_validos
            FROM fact_votos_nacional
            WHERE election_year=2026 AND vuelta=1 AND es_especial=0
            ORDER BY votos DESC
        """,
    )

    r(
        "Resultados nacionales 2v2026 (con pct pre-calculado)",
        "Nacional",
        oltp_sql="""
            SELECT v.partido_id, ag.nombre,
                   SUM(v.votos) AS total_votos,
                   ROUND(100.0*SUM(v.votos)/SUM(SUM(v.votos)) OVER(), 4) AS pct
            FROM votos_sv v
            JOIN agrupaciones_sv ag ON ag.partido_id = v.partido_id
            WHERE v.partido_id NOT IN ('80','81','82')
            GROUP BY v.partido_id, ag.nombre
            ORDER BY total_votos DESC
        """,
        denorm_sql="""
            SELECT partido_id, nombre_partido, candidato,
                   votos, pct_votos_validos, pct_votos_emitidos
            FROM fact_votos_nacional
            WHERE election_year=2026 AND vuelta=2 AND es_especial=0
            ORDER BY votos DESC
        """,
    )

    r(
        "Resultados nacionales 1v2021",
        "Nacional",
        oltp_sql="""
            SELECT v.partido_id, p.nombre_partido,
                   SUM(v.votos) AS total_votos
            FROM votos_2021 v
            JOIN partidos_2021 p ON p.partido_id=v.partido_id AND p.vuelta=v.vuelta
            WHERE v.vuelta=1
            GROUP BY v.partido_id
            ORDER BY total_votos DESC
        """,
        denorm_sql="""
            SELECT partido_id, nombre_partido, votos
            FROM fact_votos_nacional
            WHERE election_year=2021 AND vuelta=1 AND es_especial=0
            ORDER BY votos DESC
        """,
    )

    # ── PAÍS / EXTERIOR ───────────────────────────────────────────────────────
    r(
        "Votos extranjero por país — 2v2026 (candidatos)",
        "País exterior",
        oltp_sql="""
            SELECT u.pais, v.partido_id, ag.nombre,
                   SUM(v.votos) AS votos
            FROM votos_sv v
            JOIN mesas_sv m ON m.codigo_mesa = v.codigo_mesa
            JOIN ubicaciones_sv u ON u.ubigeo = m.id_ubigeo
            JOIN agrupaciones_sv ag ON ag.partido_id = v.partido_id
            WHERE u.continente != ''
              AND v.partido_id NOT IN ('80','81','82')
            GROUP BY u.pais, v.partido_id
            ORDER BY votos DESC
        """,
        denorm_sql="""
            SELECT pais, partido_id, nombre_partido, votos
            FROM fact_votos_ubigeo
            WHERE election_year=2026 AND vuelta=2
              AND ambito='exterior' AND es_especial=0
            GROUP BY pais, partido_id, nombre_partido
            ORDER BY votos DESC
        """,
        note="Denorm agrupa paises desde fact_votos_ubigeo",
    )

    r(
        "Votos extranjero por continente — 2v2026",
        "País exterior",
        oltp_sql="""
            SELECT u.continente, v.partido_id, ag.nombre,
                   SUM(v.votos) AS votos
            FROM votos_sv v
            JOIN mesas_sv m ON m.codigo_mesa = v.codigo_mesa
            JOIN ubicaciones_sv u ON u.ubigeo = m.id_ubigeo
            JOIN agrupaciones_sv ag ON ag.partido_id = v.partido_id
            WHERE u.continente != ''
              AND v.partido_id NOT IN ('80','81','82')
            GROUP BY u.continente, v.partido_id
            ORDER BY votos DESC
        """,
        denorm_sql="""
            SELECT continente, partido_id, nombre_partido, SUM(votos) AS votos
            FROM fact_votos_ubigeo
            WHERE election_year=2026 AND vuelta=2
              AND ambito='exterior' AND es_especial=0
            GROUP BY continente, partido_id
            ORDER BY votos DESC
        """,
    )

    r(
        "Votos en Argentina por ciudad — 2v2026",
        "País exterior",
        oltp_sql="""
            SELECT u.ciudad, v.partido_id, ag.nombre,
                   SUM(v.votos) AS votos
            FROM votos_sv v
            JOIN mesas_sv m ON m.codigo_mesa = v.codigo_mesa
            JOIN ubicaciones_sv u ON u.ubigeo = m.id_ubigeo
            JOIN agrupaciones_sv ag ON ag.partido_id = v.partido_id
            WHERE UPPER(u.pais) = 'ARGENTINA'
              AND v.partido_id NOT IN ('80','81','82')
            GROUP BY u.ciudad, v.partido_id
            ORDER BY votos DESC
        """,
        denorm_sql="""
            SELECT ciudad, partido_id, nombre_partido, votos
            FROM fact_votos_ubigeo
            WHERE election_year=2026 AND vuelta=2
              AND UPPER(pais)='ARGENTINA' AND es_especial=0
            ORDER BY votos DESC
        """,
    )

    # ── COMPARACIÓN 2026 vs 2021 ──────────────────────────────────────────────
    r(
        "Comparación Lima 1v2026 vs 1v2021 — partido 8 (Fuerza Popular)",
        "Cross-election",
        oltp_sql="""
            SELECT '2026' AS anio,
                   SUM(v.votos) AS votos
            FROM votos v
            JOIN mesas_data m ON m.codigo_mesa=v.codigo_mesa
            WHERE v.partido_id='8'
              AND SUBSTR('000000'||m.ubigeo,-6,2)='14'
            UNION ALL
            SELECT '2021',
                   SUM(v.votos)
            FROM votos_2021 v
            JOIN mesas_2021 m ON m.codigo_mesa=v.codigo_mesa AND m.vuelta=v.vuelta
            WHERE v.partido_id='K' AND v.vuelta=1
              AND UPPER(m.departamento)='LIMA'
        """,
        denorm_sql="""
            SELECT election_year, votos
            FROM fact_votos_departamento
            WHERE vuelta=1 AND cod_departamento='14'
              AND partido_id IN ('8','K')
            ORDER BY election_year DESC
        """,
        note="2021 partido_id='K' (Fuerza Popular) vs 2026 partido_id='8'",
    )

    r(
        "Resultados nacionales 1v2026 vs 1v2021 — top 5 partidos",
        "Cross-election",
        oltp_sql="""
            SELECT '2026' AS anio, partido_id, SUM(votos) as votos
            FROM votos
            WHERE partido_id NOT IN ('80','81','82')
            GROUP BY partido_id
            HAVING votos > 500000
            UNION ALL
            SELECT '2021', partido_id, SUM(votos)
            FROM votos_2021
            WHERE vuelta=1
            GROUP BY partido_id
            HAVING votos > 500000
            ORDER BY anio DESC, votos DESC
        """,
        denorm_sql="""
            SELECT election_year, partido_id, votos
            FROM fact_votos_nacional
            WHERE vuelta=1 AND es_especial=0 AND votos > 500000
            ORDER BY election_year DESC, votos DESC
        """,
    )

    r(
        "Delta de cobertura de actas por dpto: 2v2026 vs totales esperados",
        "Cross-election",
        oltp_sql="""
            SELECT SUBSTR(id_ubigeo,1,2) AS cod_dept,
                   COUNT(*) AS total,
                   SUM(CASE WHEN codigo_estado_acta='C' THEN 1 ELSE 0 END) AS cont,
                   ROUND(100.0*SUM(CASE WHEN codigo_estado_acta='C' THEN 1 ELSE 0 END)/COUNT(*),2) AS pct
            FROM mesas_sv
            GROUP BY cod_dept
            ORDER BY pct
        """,
        denorm_sql="""
            SELECT cod_departamento,
                   MAX(total_mesas) AS total,
                   MAX(mesas_contabilizadas) AS cont,
                   ROUND(100.0*MAX(mesas_contabilizadas)/NULLIF(MAX(total_mesas),0),2) AS pct
            FROM fact_votos_departamento
            WHERE election_year=2026 AND vuelta=2 AND partido_id='8'
            GROUP BY cod_departamento
            ORDER BY pct
        """,
    )

    # ── QUERIES COMPLEJAS / AGREGADAS ─────────────────────────────────────────
    r(
        "Winner por ubigeo en Lima — 1v2026 (ganador por distrito)",
        "Ranking complejo",
        oltp_sql="""
            SELECT m2.ubigeo, v2.partido_id, ag.nombre, v2.votos
            FROM (
                SELECT SUBSTR('000000'||m.ubigeo,-6) AS ubigeo,
                       MAX(v.votos) AS max_votos
                FROM votos v
                JOIN mesas_data m ON m.codigo_mesa=v.codigo_mesa
                WHERE SUBSTR('000000'||m.ubigeo,-6,2)='14'
                  AND v.partido_id NOT IN ('80','81','82')
                GROUP BY ubigeo
            ) mx
            JOIN mesas_data m2 ON SUBSTR('000000'||m2.ubigeo,-6)=mx.ubigeo
            JOIN votos v2 ON v2.codigo_mesa=m2.codigo_mesa AND v2.votos=mx.max_votos
              AND v2.partido_id NOT IN ('80','81','82')
            JOIN agrupaciones ag ON ag.partido_id=v2.partido_id
            GROUP BY mx.ubigeo
            ORDER BY mx.ubigeo
        """,
        denorm_sql="""
            SELECT ubigeo, partido_id, nombre_partido, votos
            FROM (
                SELECT ubigeo, partido_id, nombre_partido, votos,
                       RANK() OVER (PARTITION BY ubigeo ORDER BY votos DESC) AS rk
                FROM fact_votos_ubigeo
                WHERE election_year=2026 AND vuelta=1
                  AND cod_departamento='14' AND es_especial=0
            ) WHERE rk=1
            ORDER BY ubigeo
        """,
    )

    r(
        "Full scan nacional con métricas de mesa — todos los partidos 1v2026",
        "Full scan",
        oltp_sql="""
            SELECT v.partido_id,
                   SUM(v.votos) AS total_votos,
                   COUNT(DISTINCT v.codigo_mesa) AS mesas,
                   SUM(m.electores_habiles) / COUNT(DISTINCT v.partido_id) AS electores
            FROM votos v
            JOIN mesas_data m ON m.codigo_mesa=v.codigo_mesa
            GROUP BY v.partido_id
            ORDER BY total_votos DESC
        """,
        denorm_sql="""
            SELECT partido_id, votos, total_mesas, total_electores_habiles
            FROM fact_votos_nacional
            WHERE election_year=2026 AND vuelta=1
            ORDER BY votos DESC
        """,
    )

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Reporter
# ─────────────────────────────────────────────────────────────────────────────

def print_report(results: list[BenchResult]) -> None:
    categories = sorted(set(r.category for r in results))

    print()
    print("=" * 105)
    print(f"  BENCHMARK: onpe.db (OLTP) vs onpe_denorm.db (BI denorm)   |   {RUNS} runs/query, mediana")
    print("=" * 105)

    total_saved = 0.0
    all_match = True

    for cat in categories:
        cat_results = [r for r in results if r.category == cat]
        print(f"\n-- {cat} {'-'*(97-len(cat))}")
        print(f"  {'Query':<56} {'OLTP ms':>8} {'Denorm ms':>10} {'Speedup':>8}  {'Saved ms':>9}  {'Rows':>6}  {'Match'}")
        print(f"  {'-'*56} {'-'*8} {'-'*10} {'-'*8}  {'-'*9}  {'-'*6}  {'-'*5}")
        for r in cat_results:
            match_str = "OK" if r.match else f"DIFF({r.rows_oltp}/{r.rows_denorm})"
            if not r.match:
                all_match = False
            total_saved += r.saved_ms
            label = r.label[:56]
            speedup_str = f"{r.speedup:.1f}x" if r.speedup < 1000 else ">999x"
            print(
                f"  {label:<56} {r.oltp_ms:>8.1f} {r.denorm_ms:>10.1f} "
                f"{speedup_str:>8}  {r.saved_ms:>+9.1f}  {r.rows_denorm:>6}  {match_str}"
            )
            if r.note:
                print(f"  {'':56}   NOTE: {r.note}")

    # Summary
    print()
    print("=" * 105)
    total_oltp   = sum(r.oltp_ms   for r in results)
    total_denorm = sum(r.denorm_ms for r in results)
    avg_speedup  = statistics.median(r.speedup for r in results)
    max_speedup  = max(r.speedup for r in results)
    best         = max(results, key=lambda r: r.speedup)

    print(f"  Queries ejecutadas : {len(results)}")
    print(f"  Row match          : {'ALL OK' if all_match else 'SOME DIFFER (expected for cross-election joins)'}")
    print(f"  OLTP total (suma)  : {total_oltp:,.1f} ms")
    print(f"  Denorm total       : {total_denorm:,.1f} ms")
    print(f"  Tiempo ahorrado    : {total_saved:+,.1f} ms  ({100*(1-total_denorm/total_oltp):.1f}% reduccion)")
    print(f"  Speedup mediano    : {avg_speedup:.1f}x")
    print(f"  Speedup maximo     : {max_speedup:.1f}x  ({best.label[:60]})")
    print("=" * 105)
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Connecting to OLTP:  {OLTP_DB}")
    print(f"Connecting to Denorm: {DENORM_DB}")
    oltp  = sqlite3.connect(str(OLTP_DB))
    dn    = sqlite3.connect(str(DENORM_DB))

    # Warm-up (pre-load pages into OS cache)
    print("Warming up caches...")
    oltp.execute("SELECT COUNT(*) FROM votos").fetchone()
    dn.execute(  "SELECT COUNT(*) FROM fact_votos_mesa").fetchone()

    print(f"Running {RUNS} iterations per query...\n")
    results = build_benchmarks(oltp, dn)
    print_report(results)

    oltp.close()
    dn.close()


if __name__ == "__main__":
    main()
