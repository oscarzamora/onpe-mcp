#!/usr/bin/env python3
"""
build_denorm.py — Construye data/onpe_denorm.db, un modelo analítico
denormalizado con TODAS las permutaciones de:

    election_year × vuelta × codigo_mesa × partido_id × geo

Elecciones cubiertas
────────────────────
  • Primera Vuelta 2026  (datos completos ~2026-06-13)
  • Segunda Vuelta 2026  (datos parciales, ~98.25 % actas al 2026-06-14)
  • Primera Vuelta 2021  (datos completos)
  • Segunda Vuelta 2021  (datos completos)

Tablas producidas
─────────────────
  dim_eleccion            4 filas  (metadatos de cada proceso electoral)
  dim_partido             ≈ 71     (partidos por election_year+vuelta)
  dim_geo                 ≈ 2 102  (ubigeos únicos, Peru + extranjero)
  fact_votos_mesa         ≈ 6.5 M  (grain: election_year+vuelta+mesa+partido)
  fact_votos_ubigeo       ≈ 325 K  (agregado a nivel distrito)
  fact_votos_provincia    ≈ 12 K   (agregado a nivel provincia)
  fact_votos_departamento ≈ 540    (agregado a nivel departamento)
  fact_votos_nacional     ≈ 68     (nacional por partido)

Nota sobre ubigeos
──────────────────
  mesas_data almacena ubigeos sin zero-pad para depts 01-09 (ej: '10101').
  Todos los joins usan SUBSTR('000000'||ubigeo,-6) para normalizar a 6 dígitos.

Uso
───
  python scripts/build_denorm.py
  python scripts/build_denorm.py --src /ruta/source_snapshot.db --dest data/onpe_denorm.db
  python scripts/build_denorm.py --validate-only   (sólo valida, sin reconstruir)
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    print(f"[build_denorm] {msg}", flush=True)


def _elapsed(t0: float) -> str:
    return f"{time.time() - t0:.1f}s"


def _count(conn: sqlite3.Connection, table: str, where: str = "") -> int:
    sql = f"SELECT COUNT(*) FROM {table}"
    if where:
        sql += f" WHERE {where}"
    return conn.execute(sql).fetchone()[0]


# ─────────────────────────────────────────────────────────────────────────────
# DDL
# ─────────────────────────────────────────────────────────────────────────────

_TABLES: list[tuple[str, str]] = [
    ("dim_eleccion", """
    CREATE TABLE dim_eleccion (
        election_year          INTEGER NOT NULL,
        vuelta                 INTEGER NOT NULL,
        label                  TEXT    NOT NULL,
        total_mesas_fuente     INTEGER,
        data_completeness_note TEXT,
        PRIMARY KEY (election_year, vuelta)
    )"""),

    ("dim_partido", """
    CREATE TABLE dim_partido (
        election_year  INTEGER NOT NULL,
        vuelta         INTEGER NOT NULL,
        partido_id     TEXT    NOT NULL,
        nombre_partido TEXT    NOT NULL DEFAULT '',
        candidato      TEXT    NOT NULL DEFAULT '',
        -- 1 = blancos / nulos / impugnados (no son candidatos reales)
        es_especial    INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (election_year, vuelta, partido_id)
    )"""),

    ("dim_geo", """
    CREATE TABLE dim_geo (
        -- ubigeo normalizado a 6 dígitos (zero-padded)
        ubigeo           TEXT PRIMARY KEY,
        cod_provincia    TEXT NOT NULL DEFAULT '',   -- SUBSTR(ubigeo,1,4)
        cod_departamento TEXT NOT NULL DEFAULT '',   -- SUBSTR(ubigeo,1,2)
        ambito           TEXT NOT NULL DEFAULT 'peru',  -- 'peru' | 'extranjero'
        departamento     TEXT NOT NULL DEFAULT '',
        provincia        TEXT NOT NULL DEFAULT '',
        distrito         TEXT NOT NULL DEFAULT '',
        continente       TEXT NOT NULL DEFAULT '',
        pais             TEXT NOT NULL DEFAULT '',
        ciudad           TEXT NOT NULL DEFAULT ''
    )"""),

    ("fact_votos_mesa", """
    CREATE TABLE fact_votos_mesa (
        election_year    INTEGER NOT NULL,
        vuelta           INTEGER NOT NULL,
        codigo_mesa      TEXT    NOT NULL,
        -- Representación numérica de codigo_mesa para range scans eficientes.
        -- GENERATED ALWAYS → SQLite calcula automáticamente, no requiere cambio en INSERTs.
        -- Permite: WHERE mesa_num BETWEEN 1000 AND 5000  (integer B-tree, ~10x más rápido)
        mesa_num         INTEGER NOT NULL
                         GENERATED ALWAYS AS (CAST(codigo_mesa AS INTEGER)) STORED,
        -- geo (denormalizado desde dim_geo)
        ubigeo           TEXT    NOT NULL DEFAULT '',
        cod_provincia    TEXT    NOT NULL DEFAULT '',
        cod_departamento TEXT    NOT NULL DEFAULT '',
        ambito           TEXT    NOT NULL DEFAULT 'peru',
        departamento     TEXT    NOT NULL DEFAULT '',
        provincia        TEXT    NOT NULL DEFAULT '',
        distrito         TEXT    NOT NULL DEFAULT '',
        continente       TEXT    NOT NULL DEFAULT '',
        pais             TEXT    NOT NULL DEFAULT '',
        ciudad           TEXT    NOT NULL DEFAULT '',
        -- partido (denormalizado desde dim_partido)
        partido_id       TEXT    NOT NULL,
        nombre_partido   TEXT    NOT NULL DEFAULT '',
        candidato        TEXT    NOT NULL DEFAULT '',
        es_especial      INTEGER NOT NULL DEFAULT 0,
        -- votos
        votos            INTEGER NOT NULL DEFAULT 0,
        -- métricas de mesa (repetidas en todos los partidos de la misma mesa)
        electores_habiles   INTEGER,
        votos_emitidos      INTEGER,
        votos_validos       INTEGER,
        blancos             INTEGER,   -- votos_vb en 2021; m.blancos en 2026-1v; NULL en 2v-2026
        nulos               INTEGER,
        impugnados          INTEGER,
        estado_acta         TEXT    NOT NULL DEFAULT '',
        is_contabilizada    INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (election_year, vuelta, codigo_mesa, partido_id)
    )"""),

    ("fact_votos_ubigeo", """
    CREATE TABLE fact_votos_ubigeo (
        election_year           INTEGER NOT NULL,
        vuelta                  INTEGER NOT NULL,
        ubigeo                  TEXT    NOT NULL DEFAULT '',
        cod_provincia           TEXT    NOT NULL DEFAULT '',
        cod_departamento        TEXT    NOT NULL DEFAULT '',
        ambito                  TEXT    NOT NULL DEFAULT 'peru',
        departamento            TEXT    NOT NULL DEFAULT '',
        provincia               TEXT    NOT NULL DEFAULT '',
        distrito                TEXT    NOT NULL DEFAULT '',
        continente              TEXT    NOT NULL DEFAULT '',
        pais                    TEXT    NOT NULL DEFAULT '',
        ciudad                  TEXT    NOT NULL DEFAULT '',
        partido_id              TEXT    NOT NULL,
        nombre_partido          TEXT    NOT NULL DEFAULT '',
        candidato               TEXT    NOT NULL DEFAULT '',
        es_especial             INTEGER NOT NULL DEFAULT 0,
        votos                   INTEGER NOT NULL DEFAULT 0,
        total_mesas             INTEGER NOT NULL DEFAULT 0,
        mesas_contabilizadas    INTEGER NOT NULL DEFAULT 0,
        total_electores_habiles INTEGER,
        total_votos_emitidos    INTEGER,
        total_votos_validos     INTEGER,
        PRIMARY KEY (election_year, vuelta, ubigeo, partido_id)
    )"""),

    ("fact_votos_provincia", """
    CREATE TABLE fact_votos_provincia (
        election_year           INTEGER NOT NULL,
        vuelta                  INTEGER NOT NULL,
        cod_provincia           TEXT    NOT NULL DEFAULT '',
        departamento            TEXT    NOT NULL DEFAULT '',
        provincia               TEXT    NOT NULL DEFAULT '',
        partido_id              TEXT    NOT NULL,
        nombre_partido          TEXT    NOT NULL DEFAULT '',
        candidato               TEXT    NOT NULL DEFAULT '',
        es_especial             INTEGER NOT NULL DEFAULT 0,
        votos                   INTEGER NOT NULL DEFAULT 0,
        total_mesas             INTEGER NOT NULL DEFAULT 0,
        mesas_contabilizadas    INTEGER NOT NULL DEFAULT 0,
        total_electores_habiles INTEGER,
        total_votos_emitidos    INTEGER,
        total_votos_validos     INTEGER,
        PRIMARY KEY (election_year, vuelta, cod_provincia, partido_id)
    )"""),

    ("fact_votos_departamento", """
    CREATE TABLE fact_votos_departamento (
        election_year           INTEGER NOT NULL,
        vuelta                  INTEGER NOT NULL,
        cod_departamento        TEXT    NOT NULL DEFAULT '',
        departamento            TEXT    NOT NULL DEFAULT '',
        partido_id              TEXT    NOT NULL,
        nombre_partido          TEXT    NOT NULL DEFAULT '',
        candidato               TEXT    NOT NULL DEFAULT '',
        es_especial             INTEGER NOT NULL DEFAULT 0,
        votos                   INTEGER NOT NULL DEFAULT 0,
        total_mesas             INTEGER NOT NULL DEFAULT 0,
        mesas_contabilizadas    INTEGER NOT NULL DEFAULT 0,
        total_electores_habiles INTEGER,
        total_votos_emitidos    INTEGER,
        total_votos_validos     INTEGER,
        PRIMARY KEY (election_year, vuelta, cod_departamento, partido_id)
    )"""),

    ("fact_votos_nacional", """
    CREATE TABLE fact_votos_nacional (
        election_year           INTEGER NOT NULL,
        vuelta                  INTEGER NOT NULL,
        partido_id              TEXT    NOT NULL,
        nombre_partido          TEXT    NOT NULL DEFAULT '',
        candidato               TEXT    NOT NULL DEFAULT '',
        es_especial             INTEGER NOT NULL DEFAULT 0,
        votos                   INTEGER NOT NULL DEFAULT 0,
        total_mesas             INTEGER NOT NULL DEFAULT 0,
        mesas_contabilizadas    INTEGER NOT NULL DEFAULT 0,
        total_electores_habiles INTEGER,
        total_votos_emitidos    INTEGER,
        total_votos_validos     INTEGER,
        -- pct sobre votos_validos (excluyendo es_especial) — NULL para es_especial
        pct_votos_validos       REAL,
        -- pct sobre total votos emitidos (todos los partidos incl especiales)
        pct_votos_emitidos      REAL,
        PRIMARY KEY (election_year, vuelta, partido_id)
    )"""),

    # ── Exterior: agrega por país (todas las ciudades del mismo país) ─────────
    # Grain: (election_year, vuelta, continente, pais, partido_id)
    # Permite: "votos de Fuerza Popular en Argentina" sin GROUP BY en vuelo.
    ("fact_votos_pais", """
    CREATE TABLE fact_votos_pais (
        election_year           INTEGER NOT NULL,
        vuelta                  INTEGER NOT NULL,
        continente              TEXT    NOT NULL DEFAULT '',
        pais                    TEXT    NOT NULL DEFAULT '',
        partido_id              TEXT    NOT NULL,
        nombre_partido          TEXT    NOT NULL DEFAULT '',
        candidato               TEXT    NOT NULL DEFAULT '',
        es_especial             INTEGER NOT NULL DEFAULT 0,
        votos                   INTEGER NOT NULL DEFAULT 0,
        total_mesas             INTEGER NOT NULL DEFAULT 0,
        mesas_contabilizadas    INTEGER NOT NULL DEFAULT 0,
        total_electores_habiles INTEGER,
        total_votos_emitidos    INTEGER,
        total_votos_validos     INTEGER,
        PRIMARY KEY (election_year, vuelta, continente, pais, partido_id)
    )"""),
]

# ─────────────────────────────────────────────────────────────────────────────
# Normalización de ubigeo (inline SQL expression)
# ─────────────────────────────────────────────────────────────────────────────
#  SUBSTR('000000'||col,-6)  →  zero-padds a 6 dígitos
_pad = "SUBSTR('000000'||{col},-6)"


def _ubigeo(col: str) -> str:
    """Returns SQL expression that zero-pads a ubigeo column to 6 chars."""
    return _pad.format(col=col)


# ─────────────────────────────────────────────────────────────────────────────
# dim_eleccion
# ─────────────────────────────────────────────────────────────────────────────

def build_dim_eleccion(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO dim_eleccion VALUES (?,?,?,?,?)",
        [
            (2026, 1, "Primera Vuelta 2026", 92766,
             "Datos completos. Fuente: mesas_data + votos. Mesas contabilizadas = 92766."),
            (2026, 2, "Segunda Vuelta 2026", 92766,
             "Datos PARCIALES (~98.25% actas al 2026-06-14). "
             "Keiko 50.003% / Sanchez 49.997%. Fuente: mesas_sv + votos_sv."),
            (2021, 1, "Primera Vuelta 2021", 86488,
             "Datos completos. Fuente: mesas_2021(vuelta=1) + votos_2021(vuelta=1)."),
            (2021, 2, "Segunda Vuelta 2021", 86488,
             "Datos completos. Fuente: mesas_2021(vuelta=2) + votos_2021(vuelta=2). "
             "Peru Libre vs Fuerza Popular."),
        ],
    )
    conn.commit()
    _log(f"  dim_eleccion: {_count(conn, 'dim_eleccion'):,} rows")


# ─────────────────────────────────────────────────────────────────────────────
# dim_geo
# ─────────────────────────────────────────────────────────────────────────────

def build_dim_geo(conn: sqlite3.Connection) -> None:
    # Priority 1: ubigeo_reniec (canonical INEI domestic codes, always 6-char)
    conn.execute("""
    INSERT OR IGNORE INTO dim_geo
          (ubigeo, cod_provincia, cod_departamento, ambito,
           departamento, provincia, distrito)
    SELECT ubigeo,
           SUBSTR(ubigeo,1,4), SUBSTR(ubigeo,1,2), 'peru',
           UPPER(departamento), UPPER(provincia), UPPER(distrito)
    FROM   src.ubigeo_reniec
    """)

    # Priority 2: ubicaciones_sv — covers SV geo including foreign ubigeos
    #             Uses zero-padded ubigeo already (confirmed: no mesas_sv gaps)
    conn.execute("""
    INSERT OR IGNORE INTO dim_geo
          (ubigeo, cod_provincia, cod_departamento, ambito,
           departamento, provincia, distrito,
           continente, pais, ciudad)
    SELECT ubigeo,
           CASE WHEN LOWER(ambito)='peru' THEN SUBSTR(ubigeo,1,4) ELSE '' END,
           CASE WHEN LOWER(ambito)='peru' THEN SUBSTR(ubigeo,1,2) ELSE '' END,
           LOWER(ambito),
           UPPER(departamento), UPPER(provincia), UPPER(distrito),
           UPPER(COALESCE(continente,'')),
           UPPER(COALESCE(pais,'')),
           UPPER(COALESCE(ciudad,''))
    FROM   src.ubicaciones_sv
    """)

    # Priority 3: mesas_2021 embedded geo (any remaining gaps)
    conn.execute(f"""
    INSERT OR IGNORE INTO dim_geo
          (ubigeo, cod_provincia, cod_departamento, ambito,
           departamento, provincia, distrito)
    SELECT DISTINCT
           {_ubigeo('ubigeo')},
           SUBSTR({_ubigeo('ubigeo')},1,4),
           SUBSTR({_ubigeo('ubigeo')},1,2),
           'peru',
           UPPER(departamento), UPPER(provincia), UPPER(distrito)
    FROM   src.mesas_2021
    """)

    conn.execute("CREATE INDEX idx_dg_prov   ON dim_geo (cod_provincia)")
    conn.execute("CREATE INDEX idx_dg_dept   ON dim_geo (cod_departamento)")
    conn.execute("CREATE INDEX idx_dg_ambito ON dim_geo (ambito)")
    conn.commit()
    _log(f"  dim_geo: {_count(conn, 'dim_geo'):,} rows")


# ─────────────────────────────────────────────────────────────────────────────
# dim_partido
# ─────────────────────────────────────────────────────────────────────────────

_SPECIAL_IDS = ("'80'", "'81'", "'82'")
_SPECIAL_EXPR = f"CASE WHEN partido_id IN ({','.join(_SPECIAL_IDS)}) THEN 1 ELSE 0 END"


def build_dim_partido(conn: sqlite3.Connection) -> None:
    # 1v 2026 — agrupaciones (41 partidos incl. 80/81/82)
    conn.execute(f"""
    INSERT OR IGNORE INTO dim_partido
          (election_year, vuelta, partido_id, nombre_partido, es_especial)
    SELECT 2026, 1, partido_id, nombre, {_SPECIAL_EXPR}
    FROM   src.agrupaciones
    """)

    # 2v 2026 — agrupaciones_sv (5 ids: 8, 10, 80, 81, 82)
    #           candidatos hardcoded desde sv_resumen_nacional
    conn.execute(f"""
    INSERT OR IGNORE INTO dim_partido
          (election_year, vuelta, partido_id, nombre_partido, candidato, es_especial)
    SELECT 2026, 2, partido_id, nombre,
           CASE partido_id
               WHEN '8'  THEN 'KEIKO SOFIA FUJIMORI HIGUCHI'
               WHEN '10' THEN 'ROBERTO HELBERT SANCHEZ PALOMINO'
               ELSE ''
           END,
           {_SPECIAL_EXPR}
    FROM   src.agrupaciones_sv
    """)

    # 2021 — partidos_2021 has vuelta 1 y 2 (candidates only; blancos/nulos synth below)
    conn.execute("""
    INSERT OR IGNORE INTO dim_partido
          (election_year, vuelta, partido_id, nombre_partido, candidato, es_especial)
    SELECT 2021, vuelta, partido_id, nombre_partido, candidato, 0
    FROM   src.partidos_2021
    """)

    # 2021 — blancos/nulos/impugnados (embedded en mesas_2021, no en partidos_2021)
    conn.executemany(
        "INSERT OR IGNORE INTO dim_partido VALUES (?,?,?,?,?,1)",
        [
            (2021, 1, '80', 'VOTOS EN BLANCO',    ''),
            (2021, 1, '81', 'VOTOS NULOS',         ''),
            (2021, 1, '82', 'VOTOS IMPUGNADOS',    ''),
            (2021, 2, '80', 'VOTOS EN BLANCO',    ''),
            (2021, 2, '81', 'VOTOS NULOS',         ''),
            (2021, 2, '82', 'VOTOS IMPUGNADOS',    ''),
        ],
    )
    conn.commit()
    _log(f"  dim_partido: {_count(conn, 'dim_partido'):,} rows")


# ─────────────────────────────────────────────────────────────────────────────
# fact_votos_mesa helpers
# ─────────────────────────────────────────────────────────────────────────────

_GEO_COLS = """
        g.cod_provincia    AS cod_provincia,
        g.cod_departamento AS cod_departamento,
        COALESCE(g.ambito,'peru')     AS ambito,
        COALESCE(g.departamento,'')  AS departamento,
        COALESCE(g.provincia,'')     AS provincia,
        COALESCE(g.distrito,'')      AS distrito,
        COALESCE(g.continente,'')    AS continente,
        COALESCE(g.pais,'')          AS pais,
        COALESCE(g.ciudad,'')        AS ciudad"""

_GEO_COLS_FALLBACK = """
        COALESCE(g.cod_provincia,    SUBSTR({ub},1,4)) AS cod_provincia,
        COALESCE(g.cod_departamento, SUBSTR({ub},1,2)) AS cod_departamento,
        COALESCE(g.ambito,'peru')         AS ambito,
        COALESCE(g.departamento,'')       AS departamento,
        COALESCE(g.provincia,'')          AS provincia,
        COALESCE(g.distrito,'')           AS distrito,
        COALESCE(g.continente,'')         AS continente,
        COALESCE(g.pais,'')               AS pais,
        COALESCE(g.ciudad,'')             AS ciudad"""


def _geo_fallback(ub_expr: str) -> str:
    return _GEO_COLS_FALLBACK.format(ub=ub_expr)


# ─────────────────────────────────────────────────────────────────────────────
# fact_votos_mesa — 1v 2026
# ─────────────────────────────────────────────────────────────────────────────

def _insert_1v2026(conn: sqlite3.Connection) -> None:
    ub = _ubigeo("m.ubigeo")
    conn.execute(f"""
    INSERT INTO fact_votos_mesa
    SELECT
        2026, 1,
        v.codigo_mesa,
        {ub} AS ubigeo,
        {_geo_fallback(ub)},
        v.partido_id,
        COALESCE(p.nombre_partido,'') AS nombre_partido,
        COALESCE(p.candidato,'')      AS candidato,
        COALESCE(p.es_especial, 0)    AS es_especial,
        COALESCE(v.votos, 0)          AS votos,
        m.electores_habiles,
        m.votos_emitidos,
        m.votos_validos,
        m.blancos,
        m.nulos,
        m.impugnados,
        COALESCE(m.estado_acta,'')    AS estado_acta,
        CASE WHEN LOWER(COALESCE(m.estado_acta,''))='contabilizada' THEN 1 ELSE 0 END
    FROM  src.votos v
    LEFT JOIN src.mesas_data m ON v.codigo_mesa = m.codigo_mesa
    LEFT JOIN dim_geo g        ON {ub} = g.ubigeo
    LEFT JOIN dim_partido p
           ON p.election_year=2026 AND p.vuelta=1 AND p.partido_id=v.partido_id
    """)
    conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# fact_votos_mesa — 2v 2026
# ─────────────────────────────────────────────────────────────────────────────

def _insert_2v2026(conn: sqlite3.Connection) -> None:
    # mesas_sv.id_ubigeo is already 6-char (confirmed: 0 gaps vs ubicaciones_sv)
    conn.execute(f"""
    INSERT INTO fact_votos_mesa
    SELECT
        2026, 2,
        v.codigo_mesa,
        COALESCE(m.id_ubigeo,'') AS ubigeo,
        {_geo_fallback("COALESCE(m.id_ubigeo,'000000')")},
        v.partido_id,
        COALESCE(p.nombre_partido,''),
        COALESCE(p.candidato,''),
        COALESCE(p.es_especial, 0),
        COALESCE(v.votos, 0),
        m.electores_habiles,
        m.votos_emitidos,
        m.votos_validos,
        NULL,   -- blancos: no separado en mesas_sv (see votos_sv partido_id='80')
        NULL,   -- nulos
        NULL,   -- impugnados
        CASE m.codigo_estado_acta
            WHEN 'C' THEN 'Contabilizada'
            ELSE COALESCE(m.codigo_estado_acta,'')
        END,
        CASE WHEN m.codigo_estado_acta='C' THEN 1 ELSE 0 END
    FROM  src.votos_sv v
    LEFT JOIN src.mesas_sv m ON v.codigo_mesa = m.codigo_mesa
    LEFT JOIN dim_geo g      ON m.id_ubigeo   = g.ubigeo
    LEFT JOIN dim_partido p
           ON p.election_year=2026 AND p.vuelta=2 AND p.partido_id=v.partido_id
    """)
    conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# fact_votos_mesa — 2021 (ambas vueltas)
# ─────────────────────────────────────────────────────────────────────────────

def _insert_2021(conn: sqlite3.Connection, vuelta: int) -> None:
    ub = _ubigeo("m.ubigeo")

    # Candidate party votes
    conn.execute(f"""
    INSERT INTO fact_votos_mesa
    SELECT
        2021, {vuelta},
        v.codigo_mesa,
        {ub} AS ubigeo,
        COALESCE(g.cod_provincia,    SUBSTR({ub},1,4)),
        COALESCE(g.cod_departamento, SUBSTR({ub},1,2)),
        COALESCE(g.ambito,'peru'),
        COALESCE(g.departamento, UPPER(COALESCE(m.departamento,''))),
        COALESCE(g.provincia,    UPPER(COALESCE(m.provincia,''))),
        COALESCE(g.distrito,     UPPER(COALESCE(m.distrito,''))),
        COALESCE(g.continente,''),
        COALESCE(g.pais,''),
        COALESCE(g.ciudad,''),
        v.partido_id,
        COALESCE(p.nombre_partido,''),
        COALESCE(p.candidato,''),
        COALESCE(p.es_especial, 0),
        COALESCE(v.votos, 0),
        m.n_elec_habil,
        m.votos_emitidos,
        m.votos_validos,
        m.votos_vb,   -- blancos
        m.votos_vn,   -- nulos
        m.votos_vi,   -- impugnados
        COALESCE(m.descrip_estado_acta,''),
        CASE WHEN m.descrip_estado_acta LIKE '%Contabiliza%' THEN 1 ELSE 0 END
    FROM  src.votos_2021 v
    JOIN  src.mesas_2021 m
          ON  v.vuelta=m.vuelta AND v.codigo_mesa=m.codigo_mesa
    LEFT JOIN dim_geo g ON {ub} = g.ubigeo
    LEFT JOIN dim_partido p
           ON p.election_year=2021 AND p.vuelta={vuelta} AND p.partido_id=v.partido_id
    WHERE v.vuelta={vuelta}
    """)

    # Synthesize blancos / nulos / impugnados from mesas_2021 columns
    for pid, pname, vcol in [
        ('80', 'VOTOS EN BLANCO',    'm.votos_vb'),
        ('81', 'VOTOS NULOS',         'm.votos_vn'),
        ('82', 'VOTOS IMPUGNADOS',    'm.votos_vi'),
    ]:
        conn.execute(f"""
        INSERT INTO fact_votos_mesa
        SELECT
            2021, {vuelta},
            m.codigo_mesa,
            {ub},
            COALESCE(g.cod_provincia,    SUBSTR({ub},1,4)),
            COALESCE(g.cod_departamento, SUBSTR({ub},1,2)),
            COALESCE(g.ambito,'peru'),
            COALESCE(g.departamento, UPPER(COALESCE(m.departamento,''))),
            COALESCE(g.provincia,    UPPER(COALESCE(m.provincia,''))),
            COALESCE(g.distrito,     UPPER(COALESCE(m.distrito,''))),
            COALESCE(g.continente,''),
            COALESCE(g.pais,''),
            COALESCE(g.ciudad,''),
            '{pid}', '{pname}', '', 1,
            COALESCE({vcol}, 0),
            m.n_elec_habil, m.votos_emitidos, m.votos_validos,
            m.votos_vb, m.votos_vn, m.votos_vi,
            COALESCE(m.descrip_estado_acta,''),
            CASE WHEN m.descrip_estado_acta LIKE '%Contabiliza%' THEN 1 ELSE 0 END
        FROM  src.mesas_2021 m
        LEFT JOIN dim_geo g ON {ub} = g.ubigeo
        WHERE m.vuelta={vuelta}
        """)
    conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# fact_votos_mesa — indexes
# ─────────────────────────────────────────────────────────────────────────────

def _index_fact_mesa(conn: sqlite3.Connection) -> None:
    for sql in [
        # Lookup exacto por election/vuelta
        "CREATE INDEX idx_fvm_ev         ON fact_votos_mesa (election_year, vuelta)",
        # Range scan numérico de mesas: WHERE mesa_num BETWEEN x AND y
        # Es el índice más importante para queries de rango de mesas.
        "CREATE INDEX idx_fvm_mesa_num   ON fact_votos_mesa (election_year, vuelta, mesa_num)",
        # Covering index para queries de mesa+partido (el caso más frecuente en BI)
        "CREATE INDEX idx_fvm_mesa_prt   ON fact_votos_mesa (election_year, vuelta, mesa_num, partido_id, votos)",
        # Geo lookups
        "CREATE INDEX idx_fvm_ubigeo     ON fact_votos_mesa (election_year, vuelta, ubigeo)",
        "CREATE INDEX idx_fvm_dept       ON fact_votos_mesa (election_year, vuelta, cod_departamento)",
        "CREATE INDEX idx_fvm_prov       ON fact_votos_mesa (election_year, vuelta, cod_provincia)",
        # Partido lookup
        "CREATE INDEX idx_fvm_partido    ON fact_votos_mesa (election_year, vuelta, partido_id)",
        # Filtros operacionales
        "CREATE INDEX idx_fvm_especial   ON fact_votos_mesa (election_year, vuelta, es_especial)",
        "CREATE INDEX idx_fvm_cont       ON fact_votos_mesa (election_year, vuelta, is_contabilizada)",
    ]:
        conn.execute(sql)
    conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# fact_votos_mesa (orchestrator)
# ─────────────────────────────────────────────────────────────────────────────

def build_fact_mesa(conn: sqlite3.Connection) -> None:
    _log("Building fact_votos_mesa...")
    for ey, v, fn in [
        (2026, 1, _insert_1v2026),
        (2026, 2, _insert_2v2026),
        (2021, 1, lambda c: _insert_2021(c, 1)),
        (2021, 2, lambda c: _insert_2021(c, 2)),
    ]:
        t0 = time.time()
        fn(conn)
        n = _count(conn, "fact_votos_mesa",
                   f"election_year={ey} AND vuelta={v}")
        _log(f"  {ey}v{v}: {n:,} rows in {_elapsed(t0)}")

    _log("  Creating indexes on fact_votos_mesa...")
    _index_fact_mesa(conn)


# ─────────────────────────────────────────────────────────────────────────────
# fact_votos_ubigeo
# ─────────────────────────────────────────────────────────────────────────────

def build_fact_ubigeo(conn: sqlite3.Connection) -> None:
    _log("Building fact_votos_ubigeo...")
    t0 = time.time()

    # We deduplicate mesa-level metrics (electores, votos_emitidos, votos_validos)
    # before summing to avoid multiplying them by the number of parties.
    conn.execute("""
    INSERT INTO fact_votos_ubigeo
    WITH mesa_dedup AS (
        -- one row per (election_year, vuelta, codigo_mesa) — unique mesa metrics
        SELECT DISTINCT
            election_year, vuelta, codigo_mesa,
            ubigeo, cod_provincia, cod_departamento, ambito,
            departamento, provincia, distrito, continente, pais, ciudad,
            electores_habiles, votos_emitidos, votos_validos, is_contabilizada
        FROM fact_votos_mesa
    ),
    mesa_agg AS (
        -- aggregate per ubigeo: correct totals (no party-level multiply)
        SELECT
            election_year, vuelta, ubigeo,
            cod_provincia, cod_departamento, ambito,
            departamento, provincia, distrito, continente, pais, ciudad,
            COUNT(*)                              AS total_mesas,
            SUM(is_contabilizada)                 AS mesas_cont,
            SUM(COALESCE(electores_habiles,0))     AS total_elec,
            SUM(COALESCE(votos_emitidos,0))        AS total_emitidos,
            SUM(COALESCE(votos_validos,0))         AS total_validos
        FROM mesa_dedup
        GROUP BY election_year, vuelta, ubigeo,
                 cod_provincia, cod_departamento, ambito,
                 departamento, provincia, distrito, continente, pais, ciudad
    ),
    voto_agg AS (
        SELECT
            election_year, vuelta, ubigeo,
            partido_id, nombre_partido, candidato, es_especial,
            SUM(votos) AS votos
        FROM fact_votos_mesa
        GROUP BY election_year, vuelta, ubigeo,
                 partido_id, nombre_partido, candidato, es_especial
    )
    SELECT
        v.election_year, v.vuelta, v.ubigeo,
        m.cod_provincia, m.cod_departamento, m.ambito,
        m.departamento, m.provincia, m.distrito,
        m.continente, m.pais, m.ciudad,
        v.partido_id, v.nombre_partido, v.candidato, v.es_especial,
        v.votos,
        m.total_mesas, m.mesas_cont,
        NULLIF(m.total_elec, 0),
        NULLIF(m.total_emitidos, 0),
        NULLIF(m.total_validos, 0)
    FROM voto_agg v
    JOIN mesa_agg m
      ON  v.election_year = m.election_year
      AND v.vuelta        = m.vuelta
      AND v.ubigeo        = m.ubigeo
    """)

    for sql in [
        "CREATE INDEX idx_fvu_ev      ON fact_votos_ubigeo (election_year, vuelta)",
        "CREATE INDEX idx_fvu_dept    ON fact_votos_ubigeo (election_year, vuelta, cod_departamento)",
        "CREATE INDEX idx_fvu_prov    ON fact_votos_ubigeo (election_year, vuelta, cod_provincia)",
        "CREATE INDEX idx_fvu_partido ON fact_votos_ubigeo (election_year, vuelta, partido_id)",
        "CREATE INDEX idx_fvu_ubigeo  ON fact_votos_ubigeo (election_year, vuelta, ubigeo)",
        "CREATE INDEX idx_fvu_ambito  ON fact_votos_ubigeo (election_year, vuelta, ambito)",
        "CREATE INDEX idx_fvu_pais    ON fact_votos_ubigeo (election_year, vuelta, pais)",
        "CREATE INDEX idx_fvu_cont    ON fact_votos_ubigeo (election_year, vuelta, continente)",
    ]:
        conn.execute(sql)
    conn.commit()
    _log(f"  {_count(conn, 'fact_votos_ubigeo'):,} rows in {_elapsed(t0)}")


# ─────────────────────────────────────────────────────────────────────────────
# fact_votos_provincia
# ─────────────────────────────────────────────────────────────────────────────

def build_fact_provincia(conn: sqlite3.Connection) -> None:
    _log("Building fact_votos_provincia...")
    t0 = time.time()
    # Only domestic rows (ambito='peru') have a meaningful cod_provincia
    conn.execute("""
    INSERT INTO fact_votos_provincia
    SELECT
        election_year, vuelta,
        cod_provincia,
        MAX(departamento)  AS departamento,
        MAX(provincia)     AS provincia,
        partido_id,
        MAX(nombre_partido) AS nombre_partido,
        MAX(candidato)      AS candidato,
        MAX(es_especial)    AS es_especial,
        SUM(votos)          AS votos,
        SUM(total_mesas)    AS total_mesas,
        SUM(mesas_contabilizadas) AS mesas_cont,
        NULLIF(SUM(COALESCE(total_electores_habiles, 0)), 0),
        NULLIF(SUM(COALESCE(total_votos_emitidos, 0)),    0),
        NULLIF(SUM(COALESCE(total_votos_validos, 0)),     0)
    FROM  fact_votos_ubigeo
    WHERE ambito = 'peru'
      AND cod_provincia != ''
    GROUP BY election_year, vuelta, cod_provincia, partido_id
    """)
    for sql in [
        "CREATE INDEX idx_fvp_ev      ON fact_votos_provincia (election_year, vuelta)",
        "CREATE INDEX idx_fvp_dept    ON fact_votos_provincia (election_year, vuelta, departamento)",
        "CREATE INDEX idx_fvp_partido ON fact_votos_provincia (election_year, vuelta, partido_id)",
    ]:
        conn.execute(sql)
    conn.commit()
    _log(f"  {_count(conn, 'fact_votos_provincia'):,} rows in {_elapsed(t0)}")


# ─────────────────────────────────────────────────────────────────────────────
# fact_votos_departamento
# ─────────────────────────────────────────────────────────────────────────────

def build_fact_departamento(conn: sqlite3.Connection) -> None:
    _log("Building fact_votos_departamento...")
    t0 = time.time()
    conn.execute("""
    INSERT INTO fact_votos_departamento
    SELECT
        election_year, vuelta,
        cod_departamento,
        MAX(departamento)  AS departamento,
        partido_id,
        MAX(nombre_partido),
        MAX(candidato),
        MAX(es_especial),
        SUM(votos),
        SUM(total_mesas),
        SUM(mesas_contabilizadas),
        NULLIF(SUM(COALESCE(total_electores_habiles, 0)), 0),
        NULLIF(SUM(COALESCE(total_votos_emitidos, 0)),    0),
        NULLIF(SUM(COALESCE(total_votos_validos, 0)),     0)
    FROM  fact_votos_ubigeo
    WHERE ambito = 'peru'
      AND cod_departamento != ''
    GROUP BY election_year, vuelta, cod_departamento, partido_id
    """)
    for sql in [
        "CREATE INDEX idx_fvd_ev      ON fact_votos_departamento (election_year, vuelta)",
        "CREATE INDEX idx_fvd_partido ON fact_votos_departamento (election_year, vuelta, partido_id)",
    ]:
        conn.execute(sql)
    conn.commit()
    _log(f"  {_count(conn, 'fact_votos_departamento'):,} rows in {_elapsed(t0)}")


# ─────────────────────────────────────────────────────────────────────────────
# fact_votos_pais  (exterior — agregado por país)
# ─────────────────────────────────────────────────────────────────────────────

def build_fact_pais(conn: sqlite3.Connection) -> None:
    _log("Building fact_votos_pais...")
    t0 = time.time()
    conn.execute("""
    INSERT INTO fact_votos_pais
    SELECT
        election_year, vuelta,
        continente,
        pais,
        partido_id,
        MAX(nombre_partido) AS nombre_partido,
        MAX(candidato)      AS candidato,
        MAX(es_especial)    AS es_especial,
        SUM(votos)          AS votos,
        SUM(total_mesas)    AS total_mesas,
        SUM(mesas_contabilizadas) AS mesas_cont,
        NULLIF(SUM(COALESCE(total_electores_habiles, 0)), 0),
        NULLIF(SUM(COALESCE(total_votos_emitidos, 0)),    0),
        NULLIF(SUM(COALESCE(total_votos_validos, 0)),     0)
    FROM  fact_votos_ubigeo
    WHERE ambito = 'exterior'
      AND pais   != ''
    GROUP BY election_year, vuelta, continente, pais, partido_id
    """)
    for sql in [
        "CREATE INDEX idx_fvpais_ev      ON fact_votos_pais (election_year, vuelta)",
        "CREATE INDEX idx_fvpais_pais    ON fact_votos_pais (election_year, vuelta, pais)",
        "CREATE INDEX idx_fvpais_cont    ON fact_votos_pais (election_year, vuelta, continente)",
        "CREATE INDEX idx_fvpais_partido ON fact_votos_pais (election_year, vuelta, partido_id)",
    ]:
        conn.execute(sql)
    conn.commit()
    _log(f"  {_count(conn, 'fact_votos_pais'):,} rows in {_elapsed(t0)}")


# ─────────────────────────────────────────────────────────────────────────────
# fact_votos_nacional
# ─────────────────────────────────────────────────────────────────────────────

def build_fact_nacional(conn: sqlite3.Connection) -> None:
    _log("Building fact_votos_nacional...")
    t0 = time.time()
    conn.execute("""
    INSERT INTO fact_votos_nacional
    WITH agg AS (
        SELECT
            election_year, vuelta,
            partido_id,
            MAX(nombre_partido) AS nombre_partido,
            MAX(candidato)      AS candidato,
            MAX(es_especial)    AS es_especial,
            SUM(votos)          AS votos,
            SUM(total_mesas)    AS total_mesas,
            SUM(mesas_contabilizadas) AS mesas_cont,
            NULLIF(SUM(COALESCE(total_electores_habiles, 0)), 0) AS total_elec,
            NULLIF(SUM(COALESCE(total_votos_emitidos, 0)),    0) AS total_emitidos,
            NULLIF(SUM(COALESCE(total_votos_validos, 0)),     0) AS total_validos
        FROM  fact_votos_ubigeo
        GROUP BY election_year, vuelta, partido_id
    ),
    totals AS (
        SELECT
            election_year, vuelta,
            -- denominador para pct_votos_validos: sólo votos de candidatos reales
            SUM(CASE WHEN es_especial=0 THEN votos ELSE 0 END) AS sum_validos,
            SUM(votos) AS sum_todos
        FROM agg
        GROUP BY election_year, vuelta
    )
    SELECT
        a.election_year, a.vuelta,
        a.partido_id, a.nombre_partido, a.candidato, a.es_especial,
        a.votos,
        a.total_mesas, a.mesas_cont,
        a.total_elec, a.total_emitidos, a.total_validos,
        CASE WHEN a.es_especial=0 AND t.sum_validos > 0
             THEN ROUND(100.0 * a.votos / t.sum_validos, 4)
             ELSE NULL
        END AS pct_votos_validos,
        CASE WHEN t.sum_todos > 0
             THEN ROUND(100.0 * a.votos / t.sum_todos, 4)
             ELSE NULL
        END AS pct_votos_emitidos
    FROM agg a
    JOIN totals t ON a.election_year=t.election_year AND a.vuelta=t.vuelta
    """)
    conn.commit()
    _log(f"  {_count(conn, 'fact_votos_nacional'):,} rows in {_elapsed(t0)}")


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate(conn: sqlite3.Connection) -> dict[str, bool]:
    _log("=" * 65)
    _log("VALIDATION CHECKS")
    _log("=" * 65)
    results: dict[str, bool] = {}

    def check(label: str, passed: bool, detail: str = "") -> None:
        icon = "OK" if passed else "FAIL"
        suffix = f"  ({detail})" if detail else ""
        _log(f"  [{icon}] {label}{suffix}")
        results[label] = passed

    # ── 1. Total votos 1v 2026 ──────────────────────────────────────────────
    src = conn.execute("SELECT SUM(votos) FROM src.votos").fetchone()[0]
    dn  = conn.execute(
        "SELECT SUM(votos) FROM fact_votos_nacional "
        "WHERE election_year=2026 AND vuelta=1").fetchone()[0]
    check("1v2026 total votos", src == dn, f"src={src:,} denorm={dn:,}")

    # ── 2. Total votos 2v 2026 ──────────────────────────────────────────────
    src = conn.execute("SELECT SUM(votos) FROM src.votos_sv").fetchone()[0]
    dn  = conn.execute(
        "SELECT SUM(votos) FROM fact_votos_nacional "
        "WHERE election_year=2026 AND vuelta=2").fetchone()[0]
    check("2v2026 total votos", src == dn, f"src={src:,} denorm={dn:,}")

    # ── 3. Total votos 1v 2021 ──────────────────────────────────────────────
    src = conn.execute(
        "SELECT SUM(votos) FROM src.votos_2021 WHERE vuelta=1").fetchone()[0]
    # Denorm: only candidate parties (es_especial=0) for fair comparison
    dn  = conn.execute(
        "SELECT SUM(votos) FROM fact_votos_nacional "
        "WHERE election_year=2021 AND vuelta=1 AND es_especial=0").fetchone()[0]
    check("1v2021 candidate votos", src == dn, f"src={src:,} denorm={dn:,}")

    # ── 4. Total votos 2v 2021 ──────────────────────────────────────────────
    src = conn.execute(
        "SELECT SUM(votos) FROM src.votos_2021 WHERE vuelta=2").fetchone()[0]
    dn  = conn.execute(
        "SELECT SUM(votos) FROM fact_votos_nacional "
        "WHERE election_year=2021 AND vuelta=2 AND es_especial=0").fetchone()[0]
    check("2v2021 candidate votos", src == dn, f"src={src:,} denorm={dn:,}")

    # ── 5. votos_by_ubigeo_partido vs fact_votos_ubigeo (1v2026, candidates) ─
    mm = conn.execute("""
    SELECT COUNT(*) FROM (
        SELECT s.ubigeo, s.partido_id, s.total_votos  AS sv,
               f.votos                                AS fv
        FROM src.votos_by_ubigeo_partido s
        JOIN fact_votos_ubigeo f
          ON  f.election_year=2026 AND f.vuelta=1
          AND f.ubigeo   = SUBSTR('000000'||s.ubigeo,-6)
          AND f.partido_id = s.partido_id
        WHERE s.total_votos != f.votos
    )
    """).fetchone()[0]
    check("1v2026 ubigeo×partido vs votos_by_ubigeo_partido", mm == 0,
          f"{mm} mismatches")

    # ── 6. sv_resumen_nacional vs fact_votos_mesa contabilizadas (2v2026) ────
    # NOTA: 2v2026 son datos PARCIALES. sv_resumen_nacional y mesas_sv son
    # snapshots de momentos distintos → pequeñas diferencias son esperadas.
    # Tolerancia: 0.1% de diferencia se acepta como brecha de actualización.
    rows = conn.execute("""
    SELECT n.partido_id, n.votos_validos AS sv_cont, f.votos AS dn_cont
    FROM src.sv_resumen_nacional n
    JOIN (
        SELECT partido_id, SUM(votos) AS votos
        FROM fact_votos_mesa
        WHERE election_year=2026 AND vuelta=2
          AND is_contabilizada=1 AND es_especial=0
        GROUP BY partido_id
    ) f ON f.partido_id = n.partido_id
    WHERE n.partido_id NOT IN ('80','81','82')
    """).fetchall()
    TOLERANCE = 0.001   # 0.1 %
    all_ok = all(
        abs(r[1] - r[2]) / max(r[1], 1) <= TOLERANCE
        for r in rows
    )
    detail = "; ".join(
        f"p{r[0]}:sv={r[1]:,}/dn={r[2]:,} ({abs(r[1]-r[2])/max(r[1],1)*100:.3f}%)"
        for r in rows
    )
    check(
        "2v2026 nacional (contabilizadas, tol=0.1%) vs sv_resumen_nacional "
        "[datos parciales — brecha de snapshot esperada]",
        all_ok, detail,
    )

    # ── 7. sv_resumen_departamentos vs fact_votos_departamento (2v2026) ─────
    mm = conn.execute("""
    SELECT COUNT(*) FROM (
        SELECT s.ubigeo, s.partido_id, s.votos_validos AS sv, f.votos AS fv
        FROM src.sv_resumen_departamentos s
        JOIN fact_votos_departamento f
          ON  f.election_year=2026 AND f.vuelta=2
          AND f.cod_departamento = SUBSTR(s.ubigeo,1,2)
          AND f.partido_id       = s.partido_id
        WHERE s.partido_id NOT IN ('80','81','82')
          AND s.votos_validos != f.votos
    )
    """).fetchone()[0]
    check("2v2026 departamento vs sv_resumen_departamentos", mm == 0,
          f"{mm} mismatches")

    # ── 8. Row count summary ─────────────────────────────────────────────────
    _log("")
    _log("Row counts per election:")
    for ey, v in [(2026,1),(2026,2),(2021,1),(2021,2)]:
        n_m = _count(conn, "fact_votos_mesa",         f"election_year={ey} AND vuelta={v}")
        n_u = _count(conn, "fact_votos_ubigeo",       f"election_year={ey} AND vuelta={v}")
        n_p = _count(conn, "fact_votos_provincia",    f"election_year={ey} AND vuelta={v}")
        n_d = _count(conn, "fact_votos_departamento", f"election_year={ey} AND vuelta={v}")
        n_n = _count(conn, "fact_votos_nacional",     f"election_year={ey} AND vuelta={v}")
        _log(f"  {ey}v{v}: mesa={n_m:,}  ubigeo={n_u:,}  "
             f"provincia={n_p:,}  dpto={n_d:,}  nac={n_n:,}")

    _log("=" * 65)
    passed = sum(results.values())
    total  = len(results)
    _log(f"Result: {passed}/{total} checks passed")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Build onpe_denorm.db")
    ap.add_argument(
        "--src",
        default=str(ROOT / "data" / "source_snapshot.db"),
        help="Ruta de la DB fuente normalizada/snapshot para construir denorm",
    )
    ap.add_argument("--dest", default=str(ROOT / "data" / "onpe_denorm.db"))
    ap.add_argument("--validate-only", action="store_true",
                    help="Only run validation against existing denorm DB")
    args = ap.parse_args()

    src_path  = Path(args.src)
    dest_path = Path(args.dest)

    if not src_path.exists():
        print(f"ERROR: source DB not found: {src_path}", file=sys.stderr)
        sys.exit(1)

    if args.validate_only:
        if not dest_path.exists():
            print(f"ERROR: dest DB not found for validate-only: {dest_path}",
                  file=sys.stderr)
            sys.exit(1)
        conn = sqlite3.connect(str(dest_path))
        conn.execute(f"ATTACH DATABASE '{src_path}' AS src")
        results = validate(conn)
        conn.close()
        sys.exit(0 if all(results.values()) else 1)

    # Full build
    if dest_path.exists():
        _log(f"Removing existing {dest_path.name}...")
        dest_path.unlink()
        # Remove WAL/SHM files if present
        for suffix in ("-wal", "-shm"):
            p = dest_path.with_suffix(dest_path.suffix + suffix)
            if p.exists():
                p.unlink()

    _log(f"Building {dest_path.name} from {src_path.name}...")
    t_total = time.time()

    conn = sqlite3.connect(str(dest_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-131072")   # 128 MB page cache
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute(f"ATTACH DATABASE '{src_path}' AS src")

    # Create schema
    for table_name, ddl in _TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.execute(ddl)
    conn.commit()

    # Build dimensions
    _log("Building dimensions...")
    build_dim_eleccion(conn)
    build_dim_geo(conn)
    build_dim_partido(conn)

    # Build fact tables
    build_fact_mesa(conn)
    build_fact_ubigeo(conn)
    build_fact_provincia(conn)
    build_fact_departamento(conn)
    build_fact_pais(conn)
    build_fact_nacional(conn)

    # Validate
    results = validate(conn)

    conn.close()

    size_mb = dest_path.stat().st_size / 1_048_576
    _log(f"\nDone in {_elapsed(t_total)}. File size: {size_mb:.1f} MB")

    if not all(results.values()):
        _log("WARNING: Some validation checks failed — review output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
