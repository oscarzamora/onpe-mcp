"""Inspect ubigeo table format."""
import sqlite3
from onpe_mcp.config import Settings

conn = sqlite3.connect(Settings.from_env().data_dir / "onpe.db")
conn.row_factory = sqlite3.Row

for u in ["010603", "10603", "01-06-03"]:
    r = conn.execute(
        "SELECT * FROM ubigeo_onpe_api WHERE ubigeo = ?", (u,)
    ).fetchone()
    print(f"ubigeo_onpe_api {u!r}: {dict(r) if r else None}")
    r = conn.execute(
        "SELECT * FROM ubigeo_reniec WHERE ubigeo = ?", (u,)
    ).fetchone()
    print(f"ubigeo_reniec   {u!r}: {dict(r) if r else None}")

# Counts
c1 = conn.execute("SELECT COUNT(*) AS c FROM ubigeo_onpe_api").fetchone()
print(f"\nubigeo_onpe_api total: {c1['c']}")
c2 = conn.execute("SELECT COUNT(*) AS c FROM ubigeo_reniec").fetchone()
print(f"ubigeo_reniec   total: {c2['c']}")

# Amazonas sample
rows = conn.execute(
    "SELECT ubigeo, distrito, provincia, departamento "
    "FROM ubigeo_onpe_api WHERE departamento LIKE 'Amaz%' LIMIT 8"
).fetchall()
print("\nubigeo_onpe_api Amazonas sample:")
for r in rows:
    print(" ", dict(r))

rows = conn.execute(
    "SELECT ubigeo, distrito, provincia, departamento "
    "FROM ubigeo_reniec WHERE departamento LIKE 'AMAZ%' LIMIT 8"
).fetchall()
print("\nubigeo_reniec Amazonas sample:")
for r in rows:
    print(" ", dict(r))

# Inspect mesas_data ubigeo formats
rows = conn.execute(
    "SELECT DISTINCT LENGTH(ubigeo) AS L, COUNT(*) AS c "
    "FROM mesas_data GROUP BY L ORDER BY L"
).fetchall()
print("\nLength distribution of mesas_data.ubigeo:")
for r in rows:
    print(" ", dict(r))

# Sample mesa rural ubigeos starting w/ 1
rows = conn.execute(
    "SELECT codigo_mesa, ubigeo, local_votacion FROM mesas_data "
    "WHERE codigo_mesa LIKE '900%' AND LENGTH(ubigeo) = 5 LIMIT 5"
).fetchall()
print("\nmesas_data 900XXX with 5-digit ubigeo (rural Amazonas/Ancash):")
for r in rows:
    print(" ", dict(r))
