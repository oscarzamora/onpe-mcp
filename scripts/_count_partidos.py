"""Quick count of parties in 2026 1V."""
from __future__ import annotations

import sqlite3
from onpe_mcp.config import Settings

s = Settings.from_env()
conn = sqlite3.connect(s.data_dir / "onpe.db")
conn.row_factory = sqlite3.Row

total = conn.execute(
    "SELECT COUNT(DISTINCT partido_id) AS n FROM agrupaciones"
).fetchone()
print(f"Total partidos en agrupaciones (2026 1V): {total['n']}")

real = conn.execute(
    "SELECT COUNT(DISTINCT partido_id) AS n FROM agrupaciones "
    "WHERE partido_id NOT IN ('80','81','82')"
).fetchone()
print(f"  Excluyendo 80(blanco), 81(nulo), 82(impug): {real['n']} partidos reales")

print()
print("Lista completa:")
rows = conn.execute(
    "SELECT partido_id, nombre FROM agrupaciones "
    "ORDER BY CAST(partido_id AS INT)"
).fetchall()
for r in rows:
    print(f"  {r['partido_id']:>3}  {r['nombre']}")

conn.close()
