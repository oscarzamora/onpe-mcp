"""Explore the 900K mesa block in the 2021 SQLite cache.

Mesa codes starting with '9' historically map to overseas voting locations
in Peru (UBIGEO convention). This script summarises coverage and top
candidates by round across that block.
"""
from __future__ import annotations

import sqlite3

from onpe_mcp.config import Settings


def main() -> None:
    settings = Settings.from_env()
    conn = sqlite3.connect(settings.data_dir / "onpe.db")
    conn.row_factory = sqlite3.Row

    print("=" * 90)
    print("BLOQUE MESAS 900K (codigo_mesa LIKE '9%') — Elecciones 2021")
    print("=" * 90)

    # Cobertura por vuelta
    for vuelta in (1, 2):
        row = conn.execute(
            """
            SELECT COUNT(*) AS mesas,
                   COUNT(DISTINCT ubigeo) AS ubigeos,
                   COUNT(DISTINCT departamento) AS dptos,
                   SUM(n_elec_habil) AS electores,
                   SUM(votos_emitidos) AS emitidos,
                   SUM(votos_validos) AS validos,
                   SUM(votos_vb) AS blancos,
                   SUM(votos_vn) AS nulos,
                   SUM(votos_vi) AS impugnados
            FROM mesas_2021
            WHERE vuelta = ? AND codigo_mesa LIKE '9%'
            """,
            (vuelta,),
        ).fetchone()
        print(f"\n--- {vuelta}ra/da vuelta ---")
        print(f"  Mesas:       {row['mesas']:>10,}")
        print(f"  Ubigeos:     {row['ubigeos']:>10,}")
        print(f"  Dptos:       {row['dptos']:>10,}")
        print(f"  Electores:   {row['electores'] or 0:>10,}")
        print(f"  Emitidos:    {row['emitidos'] or 0:>10,}")
        print(f"  Validos:     {row['validos'] or 0:>10,}")
        print(f"  Blancos:     {row['blancos'] or 0:>10,}")
        print(f"  Nulos:       {row['nulos'] or 0:>10,}")
        print(f"  Impugnados:  {row['impugnados'] or 0:>10,}")

    # Departamentos 900K
    print("\n--- Departamentos asociados al bloque 900K (1V) ---")
    rows = conn.execute(
        """
        SELECT departamento, COUNT(*) AS mesas
        FROM mesas_2021
        WHERE vuelta = 1 AND codigo_mesa LIKE '9%'
        GROUP BY departamento
        ORDER BY mesas DESC
        LIMIT 30
        """
    ).fetchall()
    for r in rows:
        print(f"  {r['departamento']:<40} {r['mesas']:>6,} mesas")

    # Top candidatos 900K 1V
    print("\n--- Top candidatos 1V en bloque 900K ---")
    rows = conn.execute(
        """
        SELECT p.candidato, p.partido_id, SUM(v.votos) AS total
        FROM votos_2021 v
        JOIN partidos_2021 p ON p.vuelta = v.vuelta AND p.partido_id = v.partido_id
        WHERE v.vuelta = 1 AND v.codigo_mesa LIKE '9%'
        GROUP BY p.partido_id
        ORDER BY total DESC
        LIMIT 18
        """
    ).fetchall()
    for i, r in enumerate(rows, 1):
        print(f"  {i:>2}. {r['candidato']:<35} ({r['partido_id']:>4})  {r['total']:>10,}")

    # Top candidatos 900K 2V
    print("\n--- Top candidatos 2V en bloque 900K ---")
    rows = conn.execute(
        """
        SELECT p.candidato, p.partido_id, SUM(v.votos) AS total
        FROM votos_2021 v
        JOIN partidos_2021 p ON p.vuelta = v.vuelta AND p.partido_id = v.partido_id
        WHERE v.vuelta = 2 AND v.codigo_mesa LIKE '9%'
        GROUP BY p.partido_id
        ORDER BY total DESC
        """
    ).fetchall()
    for i, r in enumerate(rows, 1):
        print(f"  {i:>2}. {r['candidato']:<35} ({r['partido_id']:>4})  {r['total']:>10,}")

    # Sample mesas
    print("\n--- Sample de 10 mesas 900K en 1V ---")
    rows = conn.execute(
        """
        SELECT codigo_mesa, ubigeo, departamento, provincia, distrito,
               n_elec_habil, votos_emitidos
        FROM mesas_2021
        WHERE vuelta = 1 AND codigo_mesa LIKE '9%'
        ORDER BY codigo_mesa
        LIMIT 10
        """
    ).fetchall()
    for r in rows:
        print(
            f"  {r['codigo_mesa']}  {r['ubigeo']:>8}  "
            f"{r['departamento']:<25} {r['distrito']:<25} "
            f"elec={r['n_elec_habil']:>4}  emit={r['votos_emitidos']:>4}"
        )

    conn.close()


if __name__ == "__main__":
    main()
