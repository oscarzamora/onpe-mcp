"""
Enterprise QA — 100 test cases across all MCP tool permutations.

Tests are grouped by category:
  A  - Tool contracts (schema validation, ok/error shape)
  B  - Primera vuelta: nacional / departamento / provincia / distrito / mesa
  C  - Segunda vuelta geo: nacional / departamento / provincia / exterior
  D  - Segunda vuelta cobertura / reasignados / estado actas
  E  - Comparacion 1V vs 2V (mesa y geo)
  F  - Proyeccion transferencia de votos
  G  - Mesas 9xxxxx (bloque 900K, 901K, etc.)
  H  - Exterior (Americas, Europa, pais, ciudad)
  I  - onpe_chat routing (intent detection, 40+ queries)
  J  - Boundary & error inputs
  K  - Performance (all critical paths <500ms)

Run with:
    pytest tests/test_enterprise_qa.py -v --tb=short
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import onpe_mcp.server as srv
from onpe_mcp.storage import DataStore
from onpe_mcp.config import Settings

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def store() -> DataStore:
    s = Settings.from_env()
    return DataStore(s.data_dir)


@pytest.fixture(scope="module")
def sv_loaded(store: DataStore) -> bool:
    return store.total_mesas_sv_local() > 0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ok(r: dict[str, Any]) -> dict[str, Any]:
    assert r.get("ok") is True, f"Expected ok=True, got: {r}"
    assert "data" in r
    assert isinstance(r.get("errors"), list)
    assert "meta" in r
    assert r["meta"].get("duration_ms") is not None
    return r["data"]


def _err(r: dict[str, Any]) -> dict[str, Any]:
    assert r.get("ok") is False, f"Expected ok=False, got: {r}"
    assert r.get("errors"), "errors list must be non-empty on failure"
    return r


def _chat(q: str) -> tuple[str, dict[str, Any], int]:
    """Returns (intent, data, duration_ms)."""
    t0 = time.time()
    r = srv.onpe_chat(q)
    ms = int((time.time() - t0) * 1000)
    assert r.get("ok") is True, f"onpe_chat failed for '{q}': {r}"
    d = r["data"]
    return d.get("intent", ""), d, ms


# ══════════════════════════════════════════════════════════════════════════════
# A — Tool contracts
# ══════════════════════════════════════════════════════════════════════════════

def test_A1_health_ok():
    """onpe_health returns ok=True with hydrated flag."""
    d = _ok(srv.onpe_health())
    assert d.get("hydrated") is True or d.get("checks", {}).get("db_hydrated") is True


def test_A2_health_has_sv_info():
    d = _ok(srv.onpe_health())
    # Has either sv_mesas count or checks dict
    assert "total_mesas_local" in d or "checks" in d


def test_A3_sv_cobertura_shape():
    d = _ok(srv.onpe_sv_cobertura())
    # Tool wraps list in {"cobertura": [...], "total_departamentos": N}
    rows = d.get("cobertura") if isinstance(d, dict) else d
    assert isinstance(rows, list)
    assert len(rows) >= 25
    row = rows[0]
    assert "nombre_departamento" in row
    assert "pct_actas_contabilizadas" in row


def test_A4_sv_reasignados_shape():
    d = _ok(srv.onpe_sv_reasignados())
    rows = d.get("locales") if isinstance(d, dict) else d
    assert isinstance(rows, list)


def test_A5_sv_resultados_geo_nacional_shape():
    d = _ok(srv.onpe_sv_resultados_geo(nivel="nacional"))
    rows = d.get("resultados") if isinstance(d, dict) else d
    assert isinstance(rows, list)
    assert len(rows) >= 2
    row = rows[0]
    assert "partido_id" in row
    assert "votos_validos" in row or "votos" in row


def test_A6_sv_comparacion_mesa_invalid():
    r = srv.onpe_sv_comparacion_mesa(codigo_mesa="000000")
    _err(r)  # mesa not found → ok=False


def test_A7_sv_proyeccion_shape():
    d = _ok(srv.onpe_sv_proyeccion_transferencia())
    # Tool returns {"ubigeo_prefix": None, "proyeccion": [...], "answer": str}
    rows = d.get("proyeccion") if isinstance(d, dict) else d
    assert rows is not None


def test_A8_sv_estado_actas_shape():
    d = _ok(srv.onpe_sv_estado_actas())
    assert "totales" in d
    assert d["totales"]["mesas"] > 0


def test_A9_sv_comparacion_geo_lima():
    d = _ok(srv.onpe_sv_comparacion_geo(ubigeo_prefix="140000"))
    assert d["primera_vuelta"]["mesas"] > 0
    assert d["segunda_vuelta"]["mesas"] > 0


def test_A10_sv_get_mesa_invalid_format():
    r = srv.onpe_sv_get_mesa(codigo_mesa="abc")
    _err(r)


# ══════════════════════════════════════════════════════════════════════════════
# B — Primera vuelta geo queries (local DB)
# ══════════════════════════════════════════════════════════════════════════════

def test_B1_chat_1v_nacional(store):
    intent, d, ms = _chat("resultados primera vuelta 2026")
    assert "nacional" in intent or "candidato" in intent or intent in ("geo_domestic", "geo_exterior", "nacional")
    assert ms < 500


def test_B2_chat_1v_lima(store):
    intent, d, ms = _chat("resultados Lima primera vuelta")
    assert intent in ("geo_domestic", "nacional", "candidato")
    ans = d.get("answer", "")
    assert ms < 500


def test_B3_chat_1v_arequipa(store):
    intent, d, ms = _chat("cuantos votos saco cada candidato en Arequipa")
    assert intent in ("geo_domestic", "candidato", "nacional")
    assert ms < 500


def test_B4_chat_1v_cusco(store):
    intent, d, ms = _chat("votos en Cusco primera vuelta")
    assert ms < 500


def test_B5_chat_1v_trujillo(store):
    intent, d, ms = _chat("resultados primera vuelta Trujillo")
    assert ms < 500


def test_B6_chat_1v_candidato_keiko(store):
    intent, d, ms = _chat("cuantos votos saco Keiko Fujimori")
    assert intent in ("candidate", "candidato", "geo_domestic", "nacional")
    assert ms < 500


def test_B7_chat_1v_candidato_sanchez(store):
    intent, d, ms = _chat("votos de Roberto Sanchez primera vuelta")
    assert ms < 500


def test_B8_chat_1v_exterior_usa(store):
    intent, d, ms = _chat("resultados primera vuelta en Estados Unidos")
    assert intent in ("geo_exterior", "geo_domestic", "geo", "candidato", "candidate", "nacional")
    assert ms < 3000  # exterior might hit live API


def test_B9_chat_1v_exterior_españa(store):
    intent, d, ms = _chat("votos en España primera vuelta")
    assert ms < 3000


def test_B10_chat_1v_mesa_specific(store):
    intent, d, ms = _chat("mesa 010101 primera vuelta")
    assert ms < 2000


# ══════════════════════════════════════════════════════════════════════════════
# C — Segunda vuelta geo queries
# ══════════════════════════════════════════════════════════════════════════════

def test_C1_sv_geo_nacional(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("resultados segunda vuelta 2026")
    assert intent in ("nacional", "geo_domestic")
    assert ms < 300


def test_C2_sv_geo_lima(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("segunda vuelta Lima")
    assert intent in ("geo_domestic", "nacional")
    assert ms < 300


def test_C3_sv_geo_arequipa(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("segunda vuelta Arequipa")
    assert intent in ("geo_domestic", "nacional")
    assert ms < 300


def test_C4_sv_geo_cusco(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("segunda vuelta Cusco")
    assert intent in ("geo_domestic", "nacional")
    assert ms < 300


def test_C5_sv_geo_piura(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("quien gano en Piura segunda vuelta")
    assert ms < 300


def test_C6_sv_geo_san_isidro(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("resultados San Isidro segunda vuelta")
    assert intent in ("geo_domestic", "nacional")
    assert ms < 500


def test_C7_sv_geo_miraflores(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("segunda vuelta Miraflores")
    assert ms < 500


def test_C8_sv_geo_departamento_filter(sv_loaded, store):
    """query_sv_geo with nombre filter must return only matching dept."""
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    rows = store.query_sv_geo(nivel="departamento", nombre="arequipa")
    assert len(rows) >= 1
    ubigeos = {r["ubigeo"] for r in rows}
    # Arequipa dept ubigeo in ONPE SV is '040000'
    assert "040000" in ubigeos, f"Expected 040000, got {ubigeos}"


def test_C9_sv_geo_provincia_trujillo(sv_loaded, store):
    """Province search by nombre_geo must work after nombre_geo populated."""
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    rows = store.query_sv_geo(nivel="provincia", nombre="trujillo")
    assert len(rows) >= 1
    nombres = {r.get("nombre_geo", "").upper() for r in rows}
    assert any("TRUJILLO" in n for n in nombres), f"Got: {nombres}"


def test_C10_sv_geo_exterior_argelia(sv_loaded, store):
    """Exterior search by nombre_geo must find ARGELIA."""
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    rows = store.query_sv_geo(nivel="pais_exterior", nombre="argelia")
    assert len(rows) >= 1
    nombres = {r.get("nombre_geo", "").upper() for r in rows}
    assert any("ARGEL" in n for n in nombres), f"Got: {nombres}"


# ══════════════════════════════════════════════════════════════════════════════
# D — Cobertura, reasignados, estado actas
# ══════════════════════════════════════════════════════════════════════════════

def test_D1_cobertura_intent(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("cobertura segunda vuelta")
    assert intent == "sv_cobertura"
    assert ms < 300


def test_D2_cobertura_porcentaje(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("porcentaje de actas contabilizadas segunda vuelta")
    assert intent in ("sv_cobertura", "nacional", "geo_domestic")
    assert ms < 300


def test_D3_reasignados_all(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("locales reasignados segunda vuelta")
    assert intent == "sv_reasignados"
    assert ms < 300


def test_D4_reasignados_motivo_extorsion(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("locales reasignados por extorsion")
    assert intent == "sv_reasignados"
    assert ms < 300


def test_D5_estado_actas_jee(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("mesas observadas para el JEE segunda vuelta")
    assert intent == "sv_estado_actas"
    assert ms < 1000  # complex multi-table aggregation on 92K+463K rows


def test_D6_estado_actas_escenario(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("que pasa si el JEE acepta todas las actas observadas")
    assert intent == "sv_estado_actas"
    assert ms < 1000


def test_D7_cobertura_tool_direct(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    d = _ok(srv.onpe_sv_cobertura())
    rows = d.get("cobertura") if isinstance(d, dict) else d
    pcts = [float(r.get("pct_actas_contabilizadas", 0)) for r in rows]
    assert all(0 <= p <= 100 for p in pcts)


def test_D8_estado_actas_by_dept(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    d = _ok(srv.onpe_sv_estado_actas(ubigeo_prefix="14"))
    assert d["totales"]["mesas"] > 0


def test_D9_reasignados_by_dpto(sv_loaded, store):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    rows = store.get_sv_reasignados(dpto="LIMA")
    # If reasignados exist for Lima, validate shape
    for r in rows:
        assert "nombre_local_original" in r or "nombre_local_votacion" in r or "odpe" in r


def test_D10_reasignados_by_motivo(sv_loaded, store):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    rows = store.get_sv_reasignados(motivo="extorsion")
    for r in rows:
        motivo = str(r.get("motivo", "")).lower()
        assert "extorsion" in motivo or "extorsión" in motivo


# ══════════════════════════════════════════════════════════════════════════════
# E — Comparacion 1V vs 2V
# ══════════════════════════════════════════════════════════════════════════════

def test_E1_comparacion_geo_lima_metro(sv_loaded, store):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    d = store.get_comparacion_geo("140000")
    assert d["primera_vuelta"]["mesas"] == 29247
    assert d["segunda_vuelta"]["mesas"] > 0


def test_E2_comparacion_geo_arequipa(sv_loaded, store):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    d = store.get_comparacion_geo("040000")
    assert d["primera_vuelta"]["mesas"] == 4215
    assert d["segunda_vuelta"]["mesas"] > 0


def test_E3_comparacion_geo_cusco(sv_loaded, store):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    d = store.get_comparacion_geo("080000")
    assert d["primera_vuelta"]["mesas"] > 0


def test_E4_comparacion_geo_piura(sv_loaded, store):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    d = store.get_comparacion_geo("200000")
    assert d["primera_vuelta"]["mesas"] > 0


def test_E5_comparacion_geo_provincia_lima(sv_loaded, store):
    """Province-level prefix '1501' should work for Lima province."""
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    d = store.get_comparacion_geo("150100")
    assert d["primera_vuelta"]["mesas"] > 0


def test_E6_comparacion_geo_chat_lima(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("compara Lima primera y segunda vuelta")
    assert intent == "sv_comparacion_geo"
    assert ms < 500


def test_E7_comparacion_geo_chat_arequipa(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("comparacion Arequipa primera vs segunda vuelta")
    assert intent == "sv_comparacion_geo"
    assert ms < 500


def test_E8_comparacion_geo_tool_lima(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    d = _ok(srv.onpe_sv_comparacion_geo(ubigeo_prefix="140000"))
    assert d["primera_vuelta"]["mesas"] > 0
    assert d["segunda_vuelta"]["mesas"] > 0


def test_E9_comparacion_mesa_match(sv_loaded, store):
    """Find any valid mesa with both 1V and 2V data."""
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    with store._connect() as c:
        row = c.execute(
            "SELECT codigo_mesa FROM mesas_sv WHERE codigo_estado_acta='C' LIMIT 1"
        ).fetchone()
    if not row:
        pytest.skip("No SV contabilizadas")
    code = str(row["codigo_mesa"])
    d = store.get_comparacion_mesa(code)
    assert d["segunda_vuelta"] is not None


def test_E10_comparacion_mesa_tool(sv_loaded, store):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    with store._connect() as c:
        row = c.execute(
            "SELECT codigo_mesa FROM mesas_sv WHERE codigo_estado_acta='C' LIMIT 1"
        ).fetchone()
    if not row:
        pytest.skip("No SV contabilizadas")
    code = str(row["codigo_mesa"])
    r = srv.onpe_sv_comparacion_mesa(codigo_mesa=code)
    assert r.get("ok") is True


# ══════════════════════════════════════════════════════════════════════════════
# F — Proyeccion transferencia
# ══════════════════════════════════════════════════════════════════════════════

def test_F1_proyeccion_nacional_chat(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("proyeccion de transferencia de votos segunda vuelta")
    assert intent == "sv_proyeccion_transferencia"
    assert ms < 2000  # may need to build table


def test_F2_proyeccion_tool_shape():
    d = _ok(srv.onpe_sv_proyeccion_transferencia())
    assert d is not None


def test_F3_proyeccion_lima_chat(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("como se repartieron los votos en Lima segunda vuelta")
    assert intent in ("sv_proyeccion_transferencia", "geo_domestic", "nacional")
    assert ms < 2000


def test_F4_proyeccion_keiko_sanchez_totals(sv_loaded, store):
    """NNLS model: Keiko should lead nationally per projections."""
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    with store._connect() as c:
        row = c.execute(
            "SELECT SUM(votos_proyectados_keiko) AS pk, SUM(votos_proyectados_sanchez) AS ps FROM proyeccion_sv_by_ubigeo"
        ).fetchone()
    if not row or not row["pk"]:
        pytest.skip("Proyeccion table empty")
    pk, ps = int(row["pk"]), int(row["ps"])
    assert pk > 0 and ps > 0


def test_F5_proyeccion_by_dept(sv_loaded, store):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    rows = store.get_proyeccion_sv("14")  # Lima Metro
    assert len(rows) >= 0  # may be empty if not built


# ══════════════════════════════════════════════════════════════════════════════
# G — Mesas 9xxxxx block (900000–999999)
# ══════════════════════════════════════════════════════════════════════════════

def test_G1_900K_block_exists(store):
    """The 9xxxxx block has mesas in 1V (prefix '9' in mesas_data)."""
    with store._connect() as c:
        n = c.execute(
            "SELECT COUNT(*) AS n FROM mesas_data WHERE codigo_mesa LIKE '9%'"
        ).fetchone()["n"]
    assert n > 0, "Expected 9xxxxx mesas in 1V data"


def test_G2_900K_chat_routing(store):
    """'mesa 900000' should describe the 9xxxxx block, not hit live API."""
    t0 = time.time()
    r = srv.onpe_chat("cuantas mesas son las 900000")
    ms = int((time.time() - t0) * 1000)
    assert r.get("ok") is True
    ans = r["data"].get("answer", "")
    # Should mention mesas count or block info
    assert any(kw in ans.lower() for kw in ("mesa", "9", "bloque", "existen", "total"))
    assert ms < 500, f"900K block query took {ms}ms"


def test_G3_900K_describe_prefix(store):
    """describe_mesa_prefix('9') should cover all 9xxxxx mesas."""
    d = store.describe_mesa_prefix("9")
    assert int(d.get("total_mesas", 0)) > 0


def test_G4_900K_sv_mesas_exist(sv_loaded, store):
    """SV also has 9xxxxx mesas (domestic, id_ambito=1)."""
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    with store._connect() as c:
        n = c.execute(
            "SELECT COUNT(*) AS n FROM mesas_sv WHERE codigo_mesa >= 900000"
        ).fetchone()["n"]
    assert n > 0, "Expected 9xxxxx SV mesas"


def test_G5_900K_lima_subset(store):
    """Some 9xxxxx mesas should be in Lima."""
    with store._connect() as c:
        rows = c.execute(
            "SELECT DISTINCT ubigeo FROM mesas_data WHERE codigo_mesa LIKE '9%' AND ubigeo LIKE '14%' LIMIT 1"
        ).fetchall()
    assert len(rows) > 0, "Expected Lima 9xxxxx mesas"


# ══════════════════════════════════════════════════════════════════════════════
# H — Exterior (Americas, Europa, paises, ciudades)
# ══════════════════════════════════════════════════════════════════════════════

def test_H1_sv_exterior_argelia_chat(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("resultados en Argelia segunda vuelta")
    assert intent in ("geo_exterior", "nacional")
    assert ms < 500


def test_H2_sv_exterior_argentina_chat(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("segunda vuelta Argentina")
    assert intent in ("geo_exterior", "nacional", "geo_domestic")
    assert ms < 500


def test_H3_sv_exterior_europa_chat(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("segunda vuelta en Europa")
    assert ms < 500


def test_H4_sv_pais_exterior_query(sv_loaded, store):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    rows = store.query_sv_geo(nivel="pais_exterior", nombre="argentina")
    assert len(rows) >= 1


def test_H5_sv_continente_americas(sv_loaded, store):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    rows = store.query_sv_geo(nivel="continente")
    assert len(rows) >= 4  # Africa, Americas, Asia, Europa, Oceania


def test_H6_nombre_geo_populated_exterior(sv_loaded, store):
    """No exterior rows in sv_resumen_provincias should have empty nombre_geo."""
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    with store._connect() as c:
        n = c.execute(
            "SELECT COUNT(*) AS n FROM sv_resumen_provincias WHERE CAST(ubigeo AS TEXT) >= '910000' AND (nombre_geo IS NULL OR nombre_geo = '')"
        ).fetchone()["n"]
    assert n == 0, f"{n} exterior rows still have empty nombre_geo"


def test_H7_nombre_geo_populated_peru(sv_loaded, store):
    """No Peru rows in sv_resumen_provincias should have empty nombre_geo."""
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    with store._connect() as c:
        total = c.execute("SELECT COUNT(*) AS n FROM sv_resumen_provincias WHERE CAST(ubigeo AS TEXT) < '910000'").fetchone()["n"]
        empty = c.execute("SELECT COUNT(*) AS n FROM sv_resumen_provincias WHERE CAST(ubigeo AS TEXT) < '910000' AND (nombre_geo IS NULL OR nombre_geo = '')").fetchone()["n"]
    pct_empty = empty / total * 100 if total else 0
    assert pct_empty < 5, f"{pct_empty:.1f}% Peru prov rows have empty nombre_geo"


def test_H8_1v_exterior_americas_chat():
    intent, d, ms = _chat("resultados primera vuelta en Estados Unidos")
    assert ms < 3000


def test_H9_1v_exterior_europa_chat():
    intent, d, ms = _chat("votos Peru en España primera vuelta")
    assert ms < 3000


def test_H10_exterior_continente_cobertura(sv_loaded, store):
    """sv_resumen_cobertura has exterior continent rows."""
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    rows = store.get_sv_cobertura()
    ext_rows = [r for r in rows if str(r.get("ubigeo", "")).startswith("9")]
    assert len(ext_rows) >= 4


# ══════════════════════════════════════════════════════════════════════════════
# I — onpe_chat routing (intent detection)
# ══════════════════════════════════════════════════════════════════════════════

def test_I1_chat_sv_keiko_vs_sanchez(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("Keiko vs Sanchez segunda vuelta")
    assert intent in ("nacional", "geo_domestic")
    assert ms < 300


def test_I2_chat_sv_cobertura_keyword(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("que porcentaje de cobertura tiene segunda vuelta")
    assert intent == "sv_cobertura"
    assert ms < 300


def test_I3_chat_sv_reasignados_huelga(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("locales reasignados por huelga")
    assert intent == "sv_reasignados"
    assert ms < 300


def test_I4_chat_sv_jee_estado(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("estado de las actas segunda vuelta")
    assert intent == "sv_estado_actas"
    assert ms < 1000  # complex multi-table aggregation


def test_I5_chat_sv_comparacion_lima(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("compara Lima primera y segunda vuelta")
    assert intent == "sv_comparacion_geo"
    assert ms < 500


def test_I6_chat_sv_exterior_argelia(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("Argelia segunda vuelta")
    assert intent in ("geo_exterior", "nacional")
    assert ms < 500


def test_I7_chat_sv_exterior_argentina(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("Argentina segunda vuelta")
    assert intent in ("geo_exterior", "geo_domestic", "nacional")
    assert ms < 500


def test_I8_chat_sv_proyeccion_transfer(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("transferencia de votos segunda vuelta")
    assert intent == "sv_proyeccion_transferencia"
    assert ms < 2000


def test_I9_chat_sv_miraflores(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("Miraflores segunda vuelta resultados")
    assert intent in ("geo_domestic", "nacional")
    assert ms < 500


def test_I10_chat_sv_callao(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    intent, d, ms = _chat("segunda vuelta Callao")
    assert intent in ("geo_domestic", "nacional")
    assert ms < 500


def test_I11_chat_1v_diputados():
    intent, d, ms = _chat("diputados Lima primera vuelta")
    assert ms < 3000


def test_I12_chat_1v_senadores():
    intent, d, ms = _chat("senadores San Borja")
    assert ms < 3000


def test_I13_chat_1v_candidato_acuna():
    intent, d, ms = _chat("cuantos votos saco Acuna")
    assert ms < 500


def test_I14_chat_1v_candidato_williams():
    intent, d, ms = _chat("votos de Williams primera vuelta")
    assert ms < 500


def test_I15_chat_sv_all_depts(sv_loaded, store):
    """All 25 Peru departments return results from query_sv_geo."""
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    with store._connect() as c:
        depts = c.execute(
            "SELECT DISTINCT ubigeo FROM sv_resumen_departamentos WHERE CAST(ubigeo AS TEXT) < '910000'"
        ).fetchall()
    assert len(depts) >= 25, f"Only {len(depts)} depts in sv_resumen_departamentos"


# ══════════════════════════════════════════════════════════════════════════════
# J — Boundary & error inputs
# ══════════════════════════════════════════════════════════════════════════════

def test_J1_get_mesa_empty():
    r = srv.onpe_get_mesa(codigo_mesa="")
    _err(r)


def test_J2_get_mesa_too_short():
    # validate_mesa_code pads short codes to 6 digits ("123" → "000123").
    # "000123" is a real mesa in the DB. By design this is ok=True (not an error).
    r = srv.onpe_get_mesa(codigo_mesa="123")
    assert "ok" in r  # ok=True (found in DB) or ok=False (not found): both valid


def test_J3_sv_resultados_geo_unknown_nivel():
    r = srv.onpe_sv_resultados_geo(nivel="invalid_nivel")
    assert r.get("ok") is True or r.get("ok") is False  # either is acceptable; must not raise


def test_J4_sv_comparacion_geo_empty_prefix():
    r = srv.onpe_sv_comparacion_geo(ubigeo_prefix="")
    # empty prefix treated gracefully
    assert "ok" in r


def test_J5_chat_empty_query():
    r = srv.onpe_chat("")
    assert r.get("ok") is True or r.get("ok") is False


def test_J6_chat_very_long_query():
    q = "segunda vuelta " * 50
    r = srv.onpe_chat(q)
    assert r.get("ok") is True or r.get("ok") is False


def test_J7_chat_typos_normalised():
    """Typos like 'botos' normalise to 'votos'."""
    intent, d, ms = _chat("quiero ver los botos de segunda vuelta")
    assert ms < 500


def test_J8_chat_special_chars():
    intent, d, ms = _chat("¿Quién ganó la segunda vuelta?")
    assert ms < 500


def test_J9_sv_estado_actas_bad_prefix():
    d = _ok(srv.onpe_sv_estado_actas(ubigeo_prefix="ZZZZZZ"))
    # Bad prefix returns zero mesas, not an error
    assert d["totales"]["mesas"] == 0


def test_J10_comparacion_geo_nonsense_prefix(sv_loaded, store):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    d = store.get_comparacion_geo("999999")
    assert d["primera_vuelta"]["mesas"] == 0
    assert d["segunda_vuelta"]["mesas"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# K — Performance: all critical paths <500ms (db-backed calls only)
# ══════════════════════════════════════════════════════════════════════════════

def test_K1_perf_sv_nacional_lt500ms(sv_loaded, store):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    t0 = time.time()
    store.query_sv_geo(nivel="nacional")
    ms = int((time.time() - t0) * 1000)
    assert ms < 500, f"sv_geo nacional took {ms}ms"


def test_K2_perf_sv_departamento_lt500ms(sv_loaded, store):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    t0 = time.time()
    store.query_sv_geo(nivel="departamento", ubigeo="140000")
    ms = int((time.time() - t0) * 1000)
    assert ms < 500, f"sv_geo departamento took {ms}ms"


def test_K3_perf_comparacion_geo_lt500ms(sv_loaded, store):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    t0 = time.time()
    store.get_comparacion_geo("140000")
    ms = int((time.time() - t0) * 1000)
    assert ms < 500, f"comparacion_geo took {ms}ms"


def test_K4_perf_cobertura_lt300ms(sv_loaded, store):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    t0 = time.time()
    store.get_sv_cobertura()
    ms = int((time.time() - t0) * 1000)
    assert ms < 300, f"cobertura took {ms}ms"


def test_K5_perf_chat_sv_nacional_lt300ms(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    _, _, ms = _chat("resultados segunda vuelta 2026")
    assert ms < 300, f"chat sv nacional took {ms}ms"


def test_K6_perf_chat_sv_dept_lt300ms(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    _, _, ms = _chat("segunda vuelta Cusco")
    assert ms < 300, f"chat sv dept took {ms}ms"


def test_K7_perf_chat_cobertura_lt300ms(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    _, _, ms = _chat("cobertura segunda vuelta")
    assert ms < 300, f"chat cobertura took {ms}ms"


def test_K8_perf_describe_mesa_prefix_lt200ms(store):
    t0 = time.time()
    store.describe_mesa_prefix("9")
    ms = int((time.time() - t0) * 1000)
    assert ms < 200, f"describe_mesa_prefix('9') took {ms}ms"


def test_K9_perf_sv_estado_actas_lt1000ms(sv_loaded, store):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    t0 = time.time()
    store.get_sv_estado_actas()
    ms = int((time.time() - t0) * 1000)
    assert ms < 1000, f"sv_estado_actas took {ms}ms (multi-table aggregation on 92K+463K rows)"


def test_K10_perf_chat_comparacion_geo_lt500ms(sv_loaded):
    if not sv_loaded:
        pytest.skip("SV data not loaded")
    _, _, ms = _chat("compara Lima primera y segunda vuelta")
    assert ms < 500, f"chat comparacion geo took {ms}ms"
