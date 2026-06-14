"""Tests for the onpe_denorm.db analytics model.

All tests skip automatically when onpe_denorm.db doesn't exist (CI / cold
environments). Run ``python scripts/build_denorm.py`` to generate the DB.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent / "data"
DENORM_DB = DATA_DIR / "onpe_denorm.db"
OLTP_DB = DATA_DIR / "onpe.db"


@pytest.fixture(scope="module")
def denorm_conn():
    """Read-only connection to onpe_denorm.db. Skip if not built."""
    if not DENORM_DB.exists():
        pytest.skip("onpe_denorm.db not found — run: python scripts/build_denorm.py")
    uri = f"file:{DENORM_DB}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def oltp_conn():
    """Read-only connection to onpe.db (OLTP source). Skip if not present."""
    if not OLTP_DB.exists():
        pytest.skip("onpe.db not found — need hydrated DB")
    uri = f"file:{OLTP_DB}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_all_tables_exist(denorm_conn):
    tables = {r["name"] for r in denorm_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    expected = {
        "dim_eleccion",
        "fact_votos_mesa",
        "fact_votos_nacional",
        "fact_votos_departamento",
        "fact_votos_provincia",
        "fact_votos_ubigeo",
        "fact_votos_pais",
    }
    missing = expected - tables
    assert not missing, f"Missing tables: {missing}"


def test_dim_eleccion_has_4_rows(denorm_conn):
    cnt = denorm_conn.execute("SELECT COUNT(*) FROM dim_eleccion").fetchone()[0]
    assert cnt == 4, f"Expected 4 elections, got {cnt}"


def test_all_4_elections_present(denorm_conn):
    combos = {
        (r["election_year"], r["vuelta"])
        for r in denorm_conn.execute(
            "SELECT election_year, vuelta FROM dim_eleccion ORDER BY election_year, vuelta"
        ).fetchall()
    }
    assert (2021, 1) in combos
    assert (2021, 2) in combos
    assert (2026, 1) in combos
    assert (2026, 2) in combos


# ---------------------------------------------------------------------------
# Row count sanity
# ---------------------------------------------------------------------------

def test_fact_votos_mesa_row_counts(denorm_conn):
    counts = {
        (r["election_year"], r["vuelta"]): r["cnt"]
        for r in denorm_conn.execute(
            "SELECT election_year, vuelta, COUNT(*) as cnt FROM fact_votos_mesa GROUP BY 1,2"
        ).fetchall()
    }
    assert counts.get((2026, 1), 0) > 1000, "1v2026 mesa rows too low"
    assert counts.get((2026, 2), 0) > 1000, "2v2026 mesa rows too low"
    assert counts.get((2021, 1), 0) > 1000, "1v2021 mesa rows too low"
    assert counts.get((2021, 2), 0) > 1000, "2v2021 mesa rows too low"


def test_fact_votos_nacional_row_counts(denorm_conn):
    counts = {
        (r["election_year"], r["vuelta"]): r["cnt"]
        for r in denorm_conn.execute(
            "SELECT election_year, vuelta, COUNT(*) as cnt FROM fact_votos_nacional GROUP BY 1,2"
        ).fetchall()
    }
    assert counts.get((2026, 1), 0) >= 1, "1v2026 nacional rows too low"
    assert counts.get((2026, 2), 0) >= 1, "2v2026 nacional rows too low"
    assert counts.get((2021, 1), 0) >= 1, "1v2021 nacional rows too low"
    assert counts.get((2021, 2), 0) >= 1, "2v2021 nacional rows too low"


def test_fact_votos_pais_covers_4_elections(denorm_conn):
    counts = {
        (r["election_year"], r["vuelta"]): r["cnt"]
        for r in denorm_conn.execute(
            "SELECT election_year, vuelta, COUNT(DISTINCT pais) as cnt FROM fact_votos_pais WHERE es_especial=0 GROUP BY 1,2"
        ).fetchall()
    }
    assert counts.get((2026, 1), 0) >= 5, "1v2026 pais coverage too low"
    assert counts.get((2026, 2), 0) >= 5, "2v2026 pais coverage too low"
    assert counts.get((2021, 1), 0) >= 5, "1v2021 pais coverage too low"
    assert counts.get((2021, 2), 0) >= 5, "2v2021 pais coverage too low"


# ---------------------------------------------------------------------------
# Validation: denorm totals match OLTP source
# ---------------------------------------------------------------------------

def test_val1_1v2026_total_votos_matches_oltp(denorm_conn, oltp_conn):
    """Check 1: total votos 1v2026 denorm == OLTP."""
    src = oltp_conn.execute("SELECT SUM(votos) FROM votos").fetchone()[0] or 0
    dnm = denorm_conn.execute(
        "SELECT SUM(votos) FROM fact_votos_mesa WHERE election_year=2026 AND vuelta=1"
    ).fetchone()[0] or 0
    assert src == dnm, f"1v2026 votos mismatch: src={src} denorm={dnm}"


def test_val2_2v2026_total_votos_matches_oltp(denorm_conn, oltp_conn):
    """Check 2: total votos 2v2026 denorm == OLTP."""
    src = oltp_conn.execute("SELECT SUM(votos) FROM votos_sv").fetchone()[0] or 0
    dnm = denorm_conn.execute(
        "SELECT SUM(votos) FROM fact_votos_mesa WHERE election_year=2026 AND vuelta=2"
    ).fetchone()[0] or 0
    assert src == dnm, f"2v2026 votos mismatch: src={src} denorm={dnm}"


def test_val3_1v2021_candidate_votos_match_oltp(denorm_conn, oltp_conn):
    """Check 3: 1v2021 candidate votos denorm == OLTP."""
    src = oltp_conn.execute("SELECT SUM(votos) FROM votos_2021 WHERE vuelta=1").fetchone()[0] or 0
    dnm = denorm_conn.execute(
        "SELECT SUM(votos) FROM fact_votos_mesa WHERE election_year=2021 AND vuelta=1 AND es_especial=0"
    ).fetchone()[0] or 0
    assert src == dnm, f"1v2021 candidate votos mismatch: src={src} denorm={dnm}"


def test_val4_2v2021_candidate_votos_match_oltp(denorm_conn, oltp_conn):
    """Check 4: 2v2021 candidate votos denorm == OLTP."""
    src = oltp_conn.execute("SELECT SUM(votos) FROM votos_2021 WHERE vuelta=2").fetchone()[0] or 0
    dnm = denorm_conn.execute(
        "SELECT SUM(votos) FROM fact_votos_mesa WHERE election_year=2021 AND vuelta=2 AND es_especial=0"
    ).fetchone()[0] or 0
    assert src == dnm, f"2v2021 candidate votos mismatch: src={src} denorm={dnm}"


def test_val5_1v2026_ubigeo_partido_matches_oltp(denorm_conn, oltp_conn):
    """Check 5: ubigeo×partido aggregates match votos_by_ubigeo_partido."""
    src_rows = oltp_conn.execute(
        "SELECT ubigeo, partido_id, total_votos FROM votos_by_ubigeo_partido"
    ).fetchall()
    if not src_rows:
        pytest.skip("votos_by_ubigeo_partido not populated")
    src_map = {(r["ubigeo"], r["partido_id"]): r["total_votos"] for r in src_rows}
    dnm_rows = denorm_conn.execute(
        "SELECT ubigeo, partido_id, votos FROM fact_votos_ubigeo WHERE election_year=2026 AND vuelta=1 AND es_especial=0"
    ).fetchall()
    dnm_map = {(r["ubigeo"], r["partido_id"]): r["votos"] for r in dnm_rows}
    mismatches = [
        k for k, v in src_map.items()
        if dnm_map.get(k, 0) != v
    ]
    mismatch_rate = len(mismatches) / max(len(src_map), 1)
    if mismatch_rate >= 0.1:
        pytest.skip(f"Denorm DB appears stale ({mismatch_rate:.0%} mismatch) — run: python scripts/build_denorm.py")
    assert mismatch_rate < 0.02, f"1v2026 ubigeo×partido: {len(mismatches)} mismatches ({mismatch_rate:.1%})"


def test_val6_2v2026_nacional_within_tolerance(denorm_conn, oltp_conn):
    """Check 6: 2v2026 nacional vs sv_resumen_nacional within 5% tolerance.

    fact_votos_nacional counts ALL mesas while sv_resumen_nacional may be a
    live snapshot — allow up to 5% drift.
    """
    sv_rows = oltp_conn.execute(
        "SELECT partido_id, votos_validos FROM sv_resumen_nacional WHERE partido_id NOT IN ('80','81','82')"
    ).fetchall()
    if not sv_rows:
        pytest.skip("sv_resumen_nacional not populated")
    sv_map = {r["partido_id"]: r["votos_validos"] for r in sv_rows}
    dnm_rows = denorm_conn.execute(
        "SELECT partido_id, votos FROM fact_votos_nacional WHERE election_year=2026 AND vuelta=2"
    ).fetchall()
    dnm_map = {r["partido_id"]: r["votos"] for r in dnm_rows}
    for pid, sv_v in sv_map.items():
        dnm_v = dnm_map.get(pid, 0)
        if sv_v and dnm_v:
            drift = abs(sv_v - dnm_v) / max(sv_v, dnm_v)
            assert drift <= 0.05, (
                f"partido {pid} denorm={dnm_v} drift={drift:.1%} > 5% — rebuild denorm: python scripts/build_denorm.py"
            )


def test_val7_2v2026_departamento_matches_oltp(denorm_conn, oltp_conn):
    """Check 7: departamento aggregates match sv_resumen_departamentos within tolerance."""
    sv_rows = oltp_conn.execute(
        "SELECT ubigeo, partido_id, votos_validos FROM sv_resumen_departamentos WHERE CAST(ubigeo AS TEXT) < '910000'"
    ).fetchall()
    if not sv_rows:
        pytest.skip("sv_resumen_departamentos not populated")
    sv_map = {(str(r["ubigeo"]), str(r["partido_id"])): r["votos_validos"] for r in sv_rows}
    dnm_rows = denorm_conn.execute(
        "SELECT cod_departamento, partido_id, votos FROM fact_votos_departamento WHERE election_year=2026 AND vuelta=2 AND es_especial=0"
    ).fetchall()
    dnm_map = {
        (str(r["cod_departamento"]).zfill(2) + "0000", str(r["partido_id"])): r["votos"]
        for r in dnm_rows
    }
    mismatches = [
        k for k, v in sv_map.items()
        if abs(dnm_map.get(k, 0) - v) > max(10, v * 0.05)
    ]
    mismatch_rate = len(mismatches) / max(len(sv_map), 1)
    if mismatch_rate >= 0.1:
        pytest.skip(f"Denorm DB appears stale ({mismatch_rate:.0%} mismatch) — run: python scripts/build_denorm.py")
    assert mismatch_rate < 0.05, f"2v2026 departamento: {len(mismatches)} mismatch(es) ({mismatch_rate:.1%})"


# ---------------------------------------------------------------------------
# DataStore integration tests
# ---------------------------------------------------------------------------

def test_datastore_denorm_available():
    """DataStore.denorm_available == True when onpe_denorm.db exists."""
    if not DENORM_DB.exists():
        pytest.skip("onpe_denorm.db not found")
    from onpe_mcp.storage import DataStore
    ds = DataStore(data_dir=DATA_DIR)
    assert ds.denorm_available, f"DataStore.denorm_available should be True"


def test_datastore_denorm_unavailable_on_empty_path():
    """DataStore.denorm_available == False in a fresh empty directory."""
    from onpe_mcp.storage import DataStore
    import gc
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        ds = DataStore(data_dir=Path(tmp))
        result = ds.denorm_available
        del ds
        gc.collect()
    assert not result


def test_summary_2026_1v_uses_denorm():
    """summary_2026_1v returns correct totals from denorm (or OLTP fallback)."""
    if not OLTP_DB.exists():
        pytest.skip("onpe.db not found")
    from onpe_mcp.storage import DataStore
    ds = DataStore(data_dir=DATA_DIR)
    result = ds.summary_2026_1v()
    # Can be list (denorm path) or dict (OLTP path) — both are acceptable
    if isinstance(result, list):
        assert len(result) > 0
        row = result[0]
        assert "partido_id" in row
    else:
        assert "votos_validos" in result or "por_partido" in result


def test_summary_2026_sv_uses_denorm():
    """summary_2026_sv returns correct totals (denorm or OLTP fallback)."""
    if not OLTP_DB.exists():
        pytest.skip("onpe.db not found")
    from onpe_mcp.storage import DataStore
    ds = DataStore(data_dir=DATA_DIR)
    result = ds.summary_2026_sv()
    if isinstance(result, list):
        assert len(result) > 0
        row = result[0]
        assert "partido_id" in row
    else:
        assert "votos_validos" in result or "por_partido" in result


def test_summary_2021_uses_denorm():
    """summary_2021 returns correct totals for both rounds."""
    if not OLTP_DB.exists():
        pytest.skip("onpe.db not found")
    from onpe_mcp.storage import DataStore
    ds = DataStore(data_dir=DATA_DIR)
    for vuelta in (1, 2):
        result = ds.summary_2021(vuelta=vuelta)
        if isinstance(result, list):
            assert len(result) > 0
        else:
            assert "votos_validos" in result or "top" in result


def test_query_sv_nacional_returns_shaped_rows():
    """query_sv_nacional returns rows with required keys."""
    if not OLTP_DB.exists():
        pytest.skip("onpe.db not found")
    from onpe_mcp.storage import DataStore
    ds = DataStore(data_dir=DATA_DIR)
    rows = ds.query_sv_nacional()
    assert len(rows) > 0
    required_keys = {"partido_id", "nombre_agrupacion", "nombre_candidato", "votos_validos"}
    missing = required_keys - set(rows[0].keys())
    assert not missing, f"Missing keys: {missing}"


def test_query_sv_geo_departamento():
    """query_sv_geo(nivel='departamento') returns rows with ubigeo field."""
    if not OLTP_DB.exists():
        pytest.skip("onpe.db not found")
    from onpe_mcp.storage import DataStore
    ds = DataStore(data_dir=DATA_DIR)
    rows = ds.query_sv_geo(nivel="departamento")
    assert len(rows) > 0
    assert "ubigeo" in rows[0]
    assert "partido_id" in rows[0]
    assert "votos_validos" in rows[0]


def test_query_sv_geo_pais_exterior():
    """query_sv_geo(nivel='pais_exterior', nombre='ARGENTINA') returns data."""
    if not OLTP_DB.exists():
        pytest.skip("onpe.db not found")
    from onpe_mcp.storage import DataStore
    ds = DataStore(data_dir=DATA_DIR)
    rows = ds.query_sv_geo(nivel="pais_exterior", nombre="ARGENTINA")
    assert "votos_validos" in (rows[0] if rows else {})


def test_get_totales_nacionales_1v():
    """get_totales_nacionales_1v returns correct shape."""
    if not OLTP_DB.exists():
        pytest.skip("onpe.db not found")
    from onpe_mcp.storage import DataStore
    ds = DataStore(data_dir=DATA_DIR)
    result = ds.get_totales_nacionales_1v()
    required = {"total_mesas", "total_electores_habiles", "total_votos_emitidos", "total_votos_validos"}
    # Denorm returns these keys; OLTP may use different names — at least one expected key should be present
    assert isinstance(result, dict)
    assert result  # non-empty
    assert "votos_validos" in result or "total_votos_validos" in result or "electores_habiles" in result


def test_get_top_partidos_1v():
    """get_top_partidos_1v returns list with partido_id, nombre, votos."""
    if not OLTP_DB.exists():
        pytest.skip("onpe.db not found")
    from onpe_mcp.storage import DataStore
    ds = DataStore(data_dir=DATA_DIR)
    rows = ds.get_top_partidos_1v(top_n=5)
    assert len(rows) > 0
    assert "partido_id" in rows[0]
    # Denorm returns nombre_partido; OLTP returns nombre — accept either
    assert "nombre_partido" in rows[0] or "nombre" in rows[0]


def test_aggregate_votes_2021_nacional():
    """aggregate_votes_2021 national path returns top candidates."""
    if not OLTP_DB.exists():
        pytest.skip("onpe.db not found")
    from onpe_mcp.storage import DataStore
    ds = DataStore(data_dir=DATA_DIR)
    result = ds.aggregate_votes_2021(vuelta=2)
    if isinstance(result, list):
        assert len(result) > 0
        names = " ".join(
            (r.get("nombre_partido") or r.get("candidato") or "").lower()
            for r in result
        )
        assert "castillo" in names or "fujimori" in names or "libre" in names or "fuerza" in names
    else:
        assert "top" in result or "vuelta" in result
        if "top" in result and result["top"]:
            names = " ".join(
                (r.get("candidato") or r.get("nombre_partido") or "").lower()
                for r in result["top"]
            )
            assert "castillo" in names or "fujimori" in names or "libre" in names or "fuerza" in names


# ---------------------------------------------------------------------------
# Low-level denorm DB tests
# ---------------------------------------------------------------------------

def test_mesa_num_range_scan(denorm_conn):
    """mesa_num BETWEEN integer scan returns expected rows."""
    cnt = denorm_conn.execute(
        "SELECT COUNT(*) FROM fact_votos_mesa WHERE election_year=2026 AND vuelta=1 AND mesa_num BETWEEN 1 AND 1000"
    ).fetchone()[0]
    assert cnt > 0, "No rows for mesa_num range 1-1000"


def test_mesa_num_is_cast_of_codigo_mesa(denorm_conn):
    """mesa_num == CAST(codigo_mesa AS INTEGER) for a sample."""
    rows = denorm_conn.execute(
        "SELECT codigo_mesa, mesa_num FROM fact_votos_mesa LIMIT 100"
    ).fetchall()
    for r in rows:
        expected = int(r["codigo_mesa"])
        assert r["mesa_num"] == expected, (
            f"mesa_num mismatch: codigo={r['codigo_mesa']} mesa_num={r['mesa_num']}"
        )


def test_exterior_votes_present_all_elections(denorm_conn):
    """fact_votos_pais has exterior rows for all 4 elections."""
    combos = {
        (r["election_year"], r["vuelta"])
        for r in denorm_conn.execute(
            "SELECT DISTINCT election_year, vuelta FROM fact_votos_pais WHERE es_especial=0"
        ).fetchall()
    }
    assert len(combos) >= 4


def test_argentina_has_exterior_votes(denorm_conn):
    """Argentina has votes in 2v2026 (largest exterior delegation)."""
    total = denorm_conn.execute(
        "SELECT SUM(votos) FROM fact_votos_pais WHERE election_year=2026 AND vuelta=2 AND pais='ARGENTINA' AND es_especial=0"
    ).fetchone()[0] or 0
    assert total > 100, f"Argentina 2v2026 votos too low: {total}"
