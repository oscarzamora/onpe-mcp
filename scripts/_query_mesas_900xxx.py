"""Inferir departamento por prefijo de ubigeo INEI (2 dígitos)."""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from onpe_mcp.config import Settings

DPTO_BY_INEI = {
    "01": "AMAZONAS",   "02": "ÁNCASH",       "03": "APURÍMAC",
    "04": "AREQUIPA",   "05": "AYACUCHO",     "06": "CAJAMARCA",
    "07": "CALLAO",     "08": "CUSCO",        "09": "HUANCAVELICA",
    "10": "HUÁNUCO",    "11": "ICA",          "12": "JUNÍN",
    "13": "LA LIBERTAD","14": "LAMBAYEQUE",   "15": "LIMA",
    "16": "LORETO",     "17": "MADRE DE DIOS","18": "MOQUEGUA",
    "19": "PASCO",      "20": "PIURA",        "21": "PUNO",
    "22": "SAN MARTÍN", "23": "TACNA",        "24": "TUMBES",
    "25": "UCAYALI",
}


def dpto_from_ubigeo(ubigeo: str) -> str:
    u = (ubigeo or "").strip()
    if not u:
        return "?"
    # 5-dígitos sin padding (ej "10201" = 0+1 → "01" = Amazonas)
    if len(u) == 5:
        key = "0" + u[0]
    elif len(u) >= 2:
        key = u[:2]
    else:
        key = u
    return DPTO_BY_INEI.get(key, f"? ({u[:2]})")


s = Settings.from_env()
conn = sqlite3.connect(s.data_dir / "onpe.db")
conn.row_factory = sqlite3.Row

print("=== 2026 1V — mesas 900xxx por departamento (inferido de ubigeo INEI) ===\n")
rows = conn.execute(
    """
    SELECT ubigeo, COUNT(*) AS mesas,
           SUM(electores_habiles) AS elect,
           SUM(votos_emitidos) AS emit
    FROM mesas_data
    WHERE codigo_mesa LIKE '900%'
    GROUP BY ubigeo
    """
).fetchall()

by_dpto = defaultdict(lambda: {"mesas": 0, "elect": 0, "emit": 0, "ubigeos": 0})
for r in rows:
    d = dpto_from_ubigeo(r["ubigeo"])
    by_dpto[d]["mesas"] += r["mesas"]
    by_dpto[d]["elect"] += r["elect"] or 0
    by_dpto[d]["emit"] += r["emit"] or 0
    by_dpto[d]["ubigeos"] += 1

print(f"  {'Departamento':<22} {'Distritos':>10} {'Mesas':>6} "
      f"{'Electores':>10} {'Emitidos':>10}")
print(f"  {'-'*22} {'-'*10} {'-'*6} {'-'*10} {'-'*10}")
total_mesas = total_elect = total_emit = 0
for d, v in sorted(by_dpto.items(), key=lambda x: -x[1]["mesas"]):
    print(f"  {d:<22} {v['ubigeos']:>10,} {v['mesas']:>6,} "
          f"{v['elect']:>10,} {v['emit']:>10,}")
    total_mesas += v["mesas"]
    total_elect += v["elect"]
    total_emit += v["emit"]
print(f"  {'TOTAL':<22} {'-':>10} {total_mesas:>6,} "
      f"{total_elect:>10,} {total_emit:>10,}")

conn.close()

