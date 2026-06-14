"""Quick sanity-check: print 1V results from the local SQLite cache.

Used after fixing _PARTY_MAP_2021_1V to verify the SQLite re-hydration produces
the expected totals (matching Wikipedia/ONPE historical figures).
"""
from __future__ import annotations

import sqlite3

from onpe_mcp.config import Settings


def main() -> None:
    settings = Settings.from_env()
    conn = sqlite3.connect(settings.data_dir / "onpe.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT p.partido_id, p.nombre_partido, p.candidato, SUM(v.votos) AS total
        FROM votos_2021 v
        JOIN partidos_2021 p ON p.vuelta = v.vuelta AND p.partido_id = v.partido_id
        WHERE v.vuelta = 1
        GROUP BY p.partido_id
        ORDER BY total DESC
        """
    ).fetchall()
    print(f"{'#':>2} {'PID':>5} {'PARTIDO':<32} {'CANDIDATO':<35} {'VOTOS':>10}")
    print("-" * 90)
    for i, r in enumerate(rows):
        print(
            f"{i+1:>2} {r['partido_id']:>5} {r['nombre_partido']:<32} "
            f"{r['candidato']:<35} {r['total']:>10,}"
        )
    conn.close()


if __name__ == "__main__":
    main()
