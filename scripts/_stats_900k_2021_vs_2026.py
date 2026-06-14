"""Statistical comparison of mesa block 9XXXXX (rural, 'mesas 900K')
between 2021 and 2026 — both rounds.

Outputs to stdout. Designed for ad-hoc analysis; not a permanent module.

Sections:
  1. Coverage summary (mesas / electores / votos by round & year).
  2. Top candidates and concentration metrics.
  3. Participation, blank/null shares (anomalies).
  4. Swing 1V → 2V per top candidate.
  5. Transfer matrix (NNLS) per year: 1V cohort → 2V outcome.
  6. 900K vs national baseline (multiplier of the leader's advantage).
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from statistics import mean, stdev

import numpy as np
from scipy.optimize import nnls

from onpe_mcp.config import Settings

LIKE_900K = "9%"  # mesa codes starting with 9


def _fetchone_int(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    if not row:
        return 0
    val = row[0]
    return int(val or 0)


def section(title: str) -> None:
    print()
    print("=" * 92)
    print(title)
    print("=" * 92)


def subsection(title: str) -> None:
    print()
    print("-" * 92)
    print(title)
    print("-" * 92)


def _coverage(conn: sqlite3.Connection, label: str, sql: str, params: tuple) -> dict:
    row = conn.execute(sql, params).fetchone()
    if not row:
        return {}
    d = dict(row)
    print(f"  [{label:<14}] mesas={d['mesas']:>7,}  electores={d['electores'] or 0:>10,}  "
          f"emitidos={d['emitidos'] or 0:>10,}  validos={d['validos'] or 0:>10,}  "
          f"blancos={d['blancos'] or 0:>8,}  nulos={d['nulos'] or 0:>7,}")
    return d


def _top_candidates_2021(conn: sqlite3.Connection, vuelta: int, mesa_filter: str) -> list[dict]:
    sql = f"""
        SELECT p.candidato AS candidato, p.partido_id AS partido_id,
               SUM(v.votos) AS total
        FROM votos_2021 v
        JOIN partidos_2021 p ON p.vuelta = v.vuelta AND p.partido_id = v.partido_id
        WHERE v.vuelta = ? AND v.codigo_mesa LIKE ?
        GROUP BY p.partido_id
        ORDER BY total DESC
    """
    return [dict(r) for r in conn.execute(sql, (vuelta, mesa_filter)).fetchall()]


def _top_candidates_2026_1v(conn: sqlite3.Connection, mesa_filter: str) -> list[dict]:
    sql = f"""
        SELECT COALESCE(a.nombre, v.partido_id) AS candidato,
               v.partido_id AS partido_id,
               SUM(v.votos) AS total
        FROM votos v
        LEFT JOIN agrupaciones a ON a.partido_id = v.partido_id
        WHERE v.codigo_mesa LIKE ?
        GROUP BY v.partido_id
        ORDER BY total DESC
    """
    return [dict(r) for r in conn.execute(sql, (mesa_filter,)).fetchall()]


def _top_candidates_2026_2v(conn: sqlite3.Connection, mesa_filter: str) -> list[dict]:
    sql = f"""
        SELECT COALESCE(a.nombre, v.partido_id) AS candidato,
               v.partido_id AS partido_id,
               SUM(v.votos) AS total
        FROM votos_sv v
        LEFT JOIN agrupaciones_sv a ON a.partido_id = v.partido_id
        WHERE v.codigo_mesa LIKE ?
        GROUP BY v.partido_id
        ORDER BY total DESC
    """
    return [dict(r) for r in conn.execute(sql, (mesa_filter,)).fetchall()]


def _print_top(label: str, rows: list[dict], limit: int = 8) -> int:
    total = sum(r["total"] for r in rows)
    print(f"\n  >> {label} (validos = {total:,})")
    for i, r in enumerate(rows[:limit], 1):
        pct = 100.0 * r["total"] / total if total else 0
        print(f"    {i:>2}. {r['candidato']:<40} {r['total']:>10,}  ({pct:5.2f}%)")
    if len(rows) > limit:
        rest = sum(r["total"] for r in rows[limit:])
        rest_pct = 100.0 * rest / total if total else 0
        print(f"    .. {len(rows)-limit} resto                                {rest:>10,}  ({rest_pct:5.2f}%)")
    return total


def herfindahl(rows: list[dict]) -> float:
    """Herfindahl-Hirschman Index (concentration). 1 = monopoly, ~0 = perfect dispersion."""
    total = sum(r["total"] for r in rows)
    if total == 0:
        return 0.0
    return sum((r["total"] / total) ** 2 for r in rows)


def effective_n(rows: list[dict]) -> float:
    """Effective number of candidates (Laakso–Taagepera). Inverse of HHI."""
    h = herfindahl(rows)
    return 1.0 / h if h > 0 else 0.0


def _participation_stats(conn: sqlite3.Connection, year: int, vuelta: int,
                         mesa_filter: str) -> dict:
    """Per-mesa participation rate (emitidos/electores)."""
    if year == 2021:
        sql = """
            SELECT votos_emitidos AS e, n_elec_habil AS h, votos_vb AS vb, votos_vn AS vn
            FROM mesas_2021
            WHERE vuelta = ? AND codigo_mesa LIKE ? AND COALESCE(n_elec_habil,0) > 0
        """
        rows = conn.execute(sql, (vuelta, mesa_filter)).fetchall()
    elif year == 2026 and vuelta == 1:
        sql = """
            SELECT votos_emitidos AS e, electores_habiles AS h, blancos AS vb, nulos AS vn
            FROM mesas_data
            WHERE codigo_mesa LIKE ? AND COALESCE(electores_habiles,0) > 0
        """
        rows = conn.execute(sql, (mesa_filter,)).fetchall()
    elif year == 2026 and vuelta == 2:
        # blancos/nulos no separados en mesas_sv: derivar = emitidos − validos
        sql = """
            SELECT votos_emitidos AS e, electores_habiles AS h,
                   (votos_emitidos - COALESCE(votos_validos,0)) AS no_valido
            FROM mesas_sv
            WHERE codigo_mesa LIKE ? AND COALESCE(electores_habiles,0) > 0
        """
        rows = conn.execute(sql, (mesa_filter,)).fetchall()
    else:
        return {}
    if not rows:
        return {}
    pcts = [(r[0] or 0) / (r[1] or 1) for r in rows]
    no_valido = []
    if year == 2026 and vuelta == 2:
        no_valido = [
            (r[2] or 0) / (r[0] or 1) for r in rows if (r[0] or 0) > 0
        ]
    else:
        no_valido = [
            ((r[2] or 0) + (r[3] or 0)) / (r[0] or 1) for r in rows if (r[0] or 0) > 0
        ]
    return {
        "n_mesas_validas": len(rows),
        "participacion_mean": mean(pcts) if pcts else 0.0,
        "participacion_std": stdev(pcts) if len(pcts) > 1 else 0.0,
        "blanco_nulo_pct_mean": mean(no_valido) if no_valido else 0.0,
        "blanco_nulo_pct_std": stdev(no_valido) if len(no_valido) > 1 else 0.0,
    }


def _print_participation(year: int, vuelta: int, mesa_filter: str,
                         stats: dict, label: str) -> None:
    print(f"  [{label:<14}] mesas_validas={stats['n_mesas_validas']:>6,}  "
          f"participacion = {stats['participacion_mean']*100:5.2f}% ± {stats['participacion_std']*100:4.2f}pp  "
          f"|  blanco+nulo/emitidos = {stats['blanco_nulo_pct_mean']*100:5.2f}% ± "
          f"{stats['blanco_nulo_pct_std']*100:4.2f}pp")


def _mesa_party_matrix_2021(conn: sqlite3.Connection, vuelta: int,
                            mesa_filter: str, party_ids: list[str]
                            ) -> tuple[list[str], np.ndarray]:
    rows = conn.execute(
        """
        SELECT codigo_mesa, partido_id, votos
        FROM votos_2021
        WHERE vuelta = ? AND codigo_mesa LIKE ?
        """,
        (vuelta, mesa_filter),
    ).fetchall()
    by_mesa: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        by_mesa[r["codigo_mesa"]][r["partido_id"]] += int(r["votos"] or 0)
    mesas_sorted = sorted(by_mesa.keys())
    M = np.zeros((len(mesas_sorted), len(party_ids)), dtype=float)
    for i, m in enumerate(mesas_sorted):
        for j, p in enumerate(party_ids):
            M[i, j] = float(by_mesa[m].get(p, 0))
    return mesas_sorted, M


def _transfer_nnls_2021(conn: sqlite3.Connection, mesa_filter: str) -> None:
    """Solve a small NNLS to estimate the share of each 1V candidate that
    flowed to Castillo / Keiko / (Blanco+Nulo) in 2V — restricted to 900K mesas.

    Model per mesa m:
        v2v_castillo_m  ≈ sum_p w_p * v1v_p_m
        v2v_keiko_m     ≈ sum_p (1 - w_p - z_p) * v1v_p_m
        v2v_no_valido_m ≈ sum_p z_p * v1v_p_m

    We fit two independent NNLS — one for Castillo, one for Keiko.
    Coefficients are bounded [0,1] by NNLS (non-negative) + per-row weights.
    """
    # Get distinct 1V party ids
    party_ids = [r[0] for r in conn.execute(
        """
        SELECT DISTINCT partido_id FROM votos_2021
        WHERE vuelta = 1 AND codigo_mesa LIKE ?
        ORDER BY partido_id
        """,
        (mesa_filter,),
    ).fetchall()]

    if not party_ids:
        print("  (no hay datos 1V 900K para el ajuste NNLS)")
        return

    mesas_1v, M1 = _mesa_party_matrix_2021(conn, 1, mesa_filter, party_ids)

    # Build 2V target vectors per mesa for Castillo (PC) and Keiko (K)
    rows2v = conn.execute(
        """
        SELECT codigo_mesa, partido_id, votos
        FROM votos_2021
        WHERE vuelta = 2 AND codigo_mesa LIKE ?
        """,
        (mesa_filter,),
    ).fetchall()
    by_mesa_2v: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows2v:
        by_mesa_2v[r["codigo_mesa"]][r["partido_id"]] += int(r["votos"] or 0)

    y_castillo = np.array([float(by_mesa_2v.get(m, {}).get("PC", 0)) for m in mesas_1v])
    y_keiko = np.array([float(by_mesa_2v.get(m, {}).get("K", 0)) for m in mesas_1v])

    # Solve NNLS
    coefs_c, _ = nnls(M1, y_castillo)
    coefs_k, _ = nnls(M1, y_keiko)

    # Lookup candidate names
    name_lookup = {
        r[0]: r[1] for r in conn.execute(
            "SELECT partido_id, candidato FROM partidos_2021 WHERE vuelta = 1"
        ).fetchall()
    }

    # Pool sizes (votos 1V por partido en 900K)
    pool = M1.sum(axis=0)

    print(f"\n  {'PID':<5} {'CANDIDATO 1V':<32} {'POOL_1V':>10} "
          f"{'→Castillo':>10} {'→Keiko':>10} {'→Otro/Bl/N':>11}")
    print(f"  {'-'*5} {'-'*32} {'-'*10} {'-'*10} {'-'*10} {'-'*11}")
    sort_idx = np.argsort(-pool)
    for j in sort_idx:
        pid = party_ids[j]
        cand = name_lookup.get(pid, pid)
        p = pool[j]
        wc = coefs_c[j]
        wk = coefs_k[j]
        # clamp + residual to "other" so each row sums to 1 visually
        wc_v = max(0.0, min(1.0, wc))
        wk_v = max(0.0, min(1.0, wk))
        if wc_v + wk_v > 1.0:
            s = wc_v + wk_v
            wc_v /= s
            wk_v /= s
        wo = max(0.0, 1.0 - wc_v - wk_v)
        print(f"  {pid:<5} {cand[:32]:<32} {int(p):>10,} "
              f"{wc_v*100:>9.1f}% {wk_v*100:>9.1f}% {wo*100:>10.1f}%")

    # Goodness of fit (R^2)
    pred_c = M1 @ coefs_c
    pred_k = M1 @ coefs_k
    ss_res_c = float(((y_castillo - pred_c) ** 2).sum())
    ss_tot_c = float(((y_castillo - y_castillo.mean()) ** 2).sum())
    ss_res_k = float(((y_keiko - pred_k) ** 2).sum())
    ss_tot_k = float(((y_keiko - y_keiko.mean()) ** 2).sum())
    r2_c = 1 - ss_res_c / ss_tot_c if ss_tot_c else 0.0
    r2_k = 1 - ss_res_k / ss_tot_k if ss_tot_k else 0.0
    print(f"\n  Bondad de ajuste NNLS — R² Castillo = {r2_c:.4f}  |  R² Keiko = {r2_k:.4f}")


def main() -> None:
    settings = Settings.from_env()
    conn = sqlite3.connect(settings.data_dir / "onpe.db")
    conn.row_factory = sqlite3.Row

    # =================================================================
    section("1) COBERTURA DEL BLOQUE 900K (códigos de mesa que inician en 9)")
    # =================================================================
    print("\n  2021 (CSV oficial PCM/ONPE, 100% contabilizadas)")
    _coverage(conn, "2021 1V",
              """SELECT COUNT(*) AS mesas, SUM(n_elec_habil) AS electores,
                    SUM(votos_emitidos) AS emitidos, SUM(votos_validos) AS validos,
                    SUM(votos_vb) AS blancos, SUM(votos_vn) AS nulos
                 FROM mesas_2021 WHERE vuelta = 1 AND codigo_mesa LIKE ?""",
              (LIKE_900K,))
    _coverage(conn, "2021 2V",
              """SELECT COUNT(*) AS mesas, SUM(n_elec_habil) AS electores,
                    SUM(votos_emitidos) AS emitidos, SUM(votos_validos) AS validos,
                    SUM(votos_vb) AS blancos, SUM(votos_vn) AS nulos
                 FROM mesas_2021 WHERE vuelta = 2 AND codigo_mesa LIKE ?""",
              (LIKE_900K,))

    print("\n  2026 (cache scraper, live)")
    _coverage(conn, "2026 1V",
              """SELECT COUNT(*) AS mesas, SUM(electores_habiles) AS electores,
                    SUM(votos_emitidos) AS emitidos, SUM(votos_validos) AS validos,
                    SUM(blancos) AS blancos, SUM(nulos) AS nulos
                 FROM mesas_data WHERE codigo_mesa LIKE ?""",
              (LIKE_900K,))
    _coverage(conn, "2026 2V",
              """SELECT COUNT(*) AS mesas, SUM(electores_habiles) AS electores,
                    SUM(votos_emitidos) AS emitidos, SUM(votos_validos) AS validos,
                    NULL AS blancos, NULL AS nulos
                 FROM mesas_sv WHERE codigo_mesa LIKE ?""",
              (LIKE_900K,))

    # =================================================================
    section("2) TOP CANDIDATOS Y CONCENTRACIÓN EN 900K (HHI, N efectivo)")
    # =================================================================
    blocks = [
        ("2021 1V", _top_candidates_2021(conn, 1, LIKE_900K)),
        ("2021 2V", _top_candidates_2021(conn, 2, LIKE_900K)),
        ("2026 1V", _top_candidates_2026_1v(conn, LIKE_900K)),
        ("2026 2V", _top_candidates_2026_2v(conn, LIKE_900K)),
    ]
    for label, rows in blocks:
        total = _print_top(label, rows, limit=8)
        h = herfindahl(rows)
        n_eff = effective_n(rows)
        print(f"  -> HHI = {h:.4f}  |  N efectivo de candidatos = {n_eff:.2f}")

    # =================================================================
    section("3) PARTICIPACIÓN + BLANCO/NULO POR MESA (media ± desviación)")
    # =================================================================
    for year, vuelta, label in [(2021, 1, "2021 1V"), (2021, 2, "2021 2V"),
                                 (2026, 1, "2026 1V"), (2026, 2, "2026 2V")]:
        stats = _participation_stats(conn, year, vuelta, LIKE_900K)
        if stats:
            _print_participation(year, vuelta, LIKE_900K, stats, label)

    # =================================================================
    section("4) SWING 1V → 2V EN 900K (cambio absoluto y multiplicador)")
    # =================================================================

    def swing(year: int, top1v: list[dict], top2v: list[dict]) -> None:
        print(f"\n  -- {year} --")
        v1 = {r["partido_id"]: r["total"] for r in top1v}
        v2 = {r["partido_id"]: r["total"] for r in top2v}
        names_lookup = {r["partido_id"]: r["candidato"] for r in top1v}
        names_lookup.update({r["partido_id"]: r["candidato"] for r in top2v})
        print(f"    {'CAND':<35} {'1V':>10} {'2V':>10} {'×':>6} {'Δ':>10}")
        for pid in v2:
            n = names_lookup.get(pid, pid)
            a = v1.get(pid, 0)
            b = v2.get(pid, 0)
            mult = (b / a) if a else float("inf")
            d = b - a
            print(f"    {n[:35]:<35} {a:>10,} {b:>10,} {mult:>5.2f}× {d:>+10,}")

    swing(2021, blocks[0][1], blocks[1][1])
    swing(2026, blocks[2][1], blocks[3][1])

    # =================================================================
    section("5) MATRIZ DE TRANSFERENCIA NNLS (2021) — bloque 900K")
    # =================================================================
    print(
        "\n  Modelo: para cada mesa rural en 900K, ¿qué fracción de votos de cada\n"
        "  candidato 1V terminó como voto válido de Castillo / Keiko en 2V?\n"
        "  Solución NNLS por candidato 2V (coeficientes no-negativos).\n"
        "  R² alto = el modelo explica bien la varianza intermesa."
    )
    _transfer_nnls_2021(conn, LIKE_900K)

    # =================================================================
    section("6) 900K vs NACIONAL — sesgo rural vs nacional")
    # =================================================================
    # 2021 2V
    nat_2v = conn.execute(
        """
        SELECT p.candidato, SUM(v.votos) AS total
        FROM votos_2021 v JOIN partidos_2021 p
          ON p.vuelta = v.vuelta AND p.partido_id = v.partido_id
        WHERE v.vuelta = 2
        GROUP BY p.partido_id
        ORDER BY total DESC
        """
    ).fetchall()
    n_total = sum(r["total"] for r in nat_2v)
    r900k_2v = blocks[1][1]
    r900k_total = sum(r["total"] for r in r900k_2v)
    print(f"\n  2021 2V — comparativo % de voto válido")
    print(f"    {'CAND':<35} {'%900K':>8} {'%NACIONAL':>10} {'BIAS_900K':>10}")
    pct_900k = {r["candidato"]: 100.0 * r["total"] / r900k_total for r in r900k_2v}
    for r in nat_2v:
        pct_n = 100.0 * r["total"] / n_total
        pct_r = pct_900k.get(r["candidato"], 0.0)
        bias = pct_r - pct_n
        print(f"    {r['candidato'][:35]:<35} {pct_r:>7.2f}% {pct_n:>9.2f}% {bias:>+9.2f}pp")

    # 2026 2V
    nat_2v26 = conn.execute(
        """
        SELECT COALESCE(a.nombre, v.partido_id) AS candidato, SUM(v.votos) AS total
        FROM votos_sv v
        LEFT JOIN agrupaciones_sv a ON a.partido_id = v.partido_id
        GROUP BY v.partido_id
        ORDER BY total DESC
        """
    ).fetchall()
    n_total26 = sum(r["total"] for r in nat_2v26)
    r900k_2v26 = blocks[3][1]
    r900k_total26 = sum(r["total"] for r in r900k_2v26)
    print(f"\n  2026 2V — comparativo % de voto válido")
    print(f"    {'CAND':<35} {'%900K':>8} {'%NACIONAL':>10} {'BIAS_900K':>10}")
    pct_900k26 = {r["candidato"]: 100.0 * r["total"] / r900k_total26 for r in r900k_2v26}
    for r in nat_2v26:
        pct_n = 100.0 * r["total"] / n_total26
        pct_r = pct_900k26.get(r["candidato"], 0.0)
        bias = pct_r - pct_n
        print(f"    {r['candidato'][:35]:<35} {pct_r:>7.2f}% {pct_n:>9.2f}% {bias:>+9.2f}pp")

    conn.close()


if __name__ == "__main__":
    main()
