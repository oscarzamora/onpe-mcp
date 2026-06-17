from __future__ import annotations

import sqlite3
from pathlib import Path

from onpe_mcp.analytics import AnalyticsEngine


def _seed_denorm_like_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE fact_votos_mesa (
          election_year INTEGER,
          vuelta INTEGER,
          codigo_mesa TEXT,
          ubigeo TEXT,
          cod_provincia TEXT,
          cod_departamento TEXT,
          ambito TEXT,
          departamento TEXT,
          provincia TEXT,
          distrito TEXT,
          continente TEXT,
          pais TEXT,
          ciudad TEXT,
          partido_id TEXT,
          nombre_partido TEXT,
          candidato TEXT,
          es_especial INTEGER,
          votos INTEGER,
          electores_habiles INTEGER,
          votos_emitidos INTEGER,
          votos_validos INTEGER,
          blancos INTEGER,
          nulos INTEGER,
          impugnados INTEGER,
          estado_acta TEXT,
          is_contabilizada INTEGER
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO fact_votos_mesa VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        [
            (2026, 2, "900001", "150101", "1501", "15", "PERU", "LIMA", "LIMA", "LIMA", "", "", "", "8", "FUERZA POPULAR", "KEIKO", 0, 0, 100, 80, 70, 5, 5, 0, "C", 1),
            (2026, 2, "900002", "150101", "1501", "15", "PERU", "LIMA", "LIMA", "LIMA", "", "", "", "8", "FUERZA POPULAR", "KEIKO", 0, 4, 100, 80, 70, 5, 5, 0, "E", 0),
            (2026, 2, "900001", "150101", "1501", "15", "PERU", "LIMA", "LIMA", "LIMA", "", "", "", "10", "JUNTOS POR EL PERU", "SANCHEZ", 0, 70, 100, 80, 70, 5, 5, 0, "C", 1),
            (2026, 2, "910001", "920101", "9201", "92", "EXTERIOR", "", "", "", "ASIA", "JAPÓN", "TOKIO", "8", "FUERZA POPULAR", "KEIKO", 0, 10, 20, 15, 15, 0, 0, 0, "C", 1),
            (2026, 2, "910001", "920101", "9201", "92", "EXTERIOR", "", "", "", "ASIA", "JAPÓN", "TOKIO", "10", "JUNTOS POR EL PERU", "SANCHEZ", 0, 5, 20, 15, 15, 0, 0, 0, "C", 1),
        ],
    )
    conn.commit()
    conn.close()


def test_query_predicate_and_pagination(tmp_path: Path) -> None:
    db_path = tmp_path / "onpe_denorm.db"
    _seed_denorm_like_db(db_path)
    engine = AnalyticsEngine(db_path)

    out = engine.query(
        {
            "dataset": "mesa",
            "election_year": 2026,
            "vuelta": 2,
            "select": ["codigo_mesa", "partido_id", "votos"],
            "where": [
                {"field": "partido_id", "op": "eq", "value": "8"},
                {"field": "votos", "op": "eq", "value": 0},
            ],
            "limit": 50,
            "offset": 0,
            "count_only_contabilizadas": True,
        }
    )

    assert out["total"] == 1
    assert out["returned"] == 1
    assert out["rows"][0]["codigo_mesa"] == "900001"
    assert out["rows"][0]["votos"] == 0
    assert out["has_more"] is False


def test_filter_mesas_resolves_party_name_and_excludes_not_contabilizadas(tmp_path: Path) -> None:
    db_path = tmp_path / "onpe_denorm.db"
    _seed_denorm_like_db(db_path)
    engine = AnalyticsEngine(db_path)

    out = engine.filter_mesas(
        election_year=2026,
        vuelta=2,
        partido="fuerza popular",
        votos_op="lte",
        votos_value=4,
        solo_escrutadas=True,
        mesa_prefix="900",
        limit=100,
        offset=0,
    )

    assert out["total"] == 1
    assert out["rows"][0]["codigo_mesa"] == "900001"
    assert out["rows"][0]["is_contabilizada"] == 1


def test_query_still_rejects_having_and_compare(tmp_path: Path) -> None:
    db_path = tmp_path / "onpe_denorm.db"
    _seed_denorm_like_db(db_path)
    engine = AnalyticsEngine(db_path)

    try:
        engine.query(
            {
                "dataset": "mesa",
                "election_year": 2026,
                "vuelta": 2,
                "select": ["codigo_mesa", "votos"],
                "having": [{"field": "votos", "op": "gt", "value": 1}],
            }
        )
        assert False, "Expected ValueError for unsupported feature"
    except ValueError as exc:
        assert "features no soportadas" in str(exc)


def test_query_supports_group_by_with_aggregates(tmp_path: Path) -> None:
    db_path = tmp_path / "onpe_denorm.db"
    _seed_denorm_like_db(db_path)
    engine = AnalyticsEngine(db_path)

    out = engine.query(
        {
            "dataset": "mesa",
            "election_year": 2026,
            "vuelta": 2,
            "select": ["nombre_partido", "sum(votos) as votos_total"],
            "where": [{"field": "pais", "op": "eq", "value": "JAPÓN"}],
            "group_by": ["nombre_partido"],
            "order_by": [{"field": "votos_total", "dir": "desc"}],
            "count_only_contabilizadas": False,
            "limit": 10,
        }
    )

    assert out["returned"] == 2
    assert out["rows"][0]["nombre_partido"] == "FUERZA POPULAR"
    assert out["rows"][0]["votos_total"] == 10
    assert out["rows"][1]["votos_total"] == 5


def test_query_supports_registered_preset(tmp_path: Path) -> None:
    db_path = tmp_path / "onpe_denorm.db"
    _seed_denorm_like_db(db_path)
    engine = AnalyticsEngine(db_path)

    out = engine.query(
        {
            "preset": "900k_segunda_vuelta_resumen",
            "select": ["codigo_mesa", "partido_id", "votos"],
            "limit": 10,
        }
    )

    assert out["query_echo"]["preset"] == "900k_segunda_vuelta_resumen"
    assert out["schema_version"] == "1.0"
    assert out["returned"] >= 1


def test_search_entities_returns_geo_and_party_candidates(tmp_path: Path) -> None:
    db_path = tmp_path / "onpe_denorm.db"
    _seed_denorm_like_db(db_path)
    engine = AnalyticsEngine(db_path)

    out = engine.search_entities(
        query="lima",
        field="any",
        election_year=2026,
        vuelta=2,
        limit=10,
    )

    assert out["returned"] >= 1
    assert any(item["type"] in {"departamento", "provincia", "distrito", "partido"} for item in out["matches"])


def test_search_entities_is_accent_insensitive(tmp_path: Path) -> None:
    db_path = tmp_path / "onpe_denorm.db"
    _seed_denorm_like_db(db_path)
    engine = AnalyticsEngine(db_path)

    out = engine.search_entities(
        query="japon",
        field="pais",
        election_year=2026,
        vuelta=2,
        limit=10,
    )

    assert out["returned"] >= 1
    assert any(item["canonical_name"] == "JAPÓN" for item in out["matches"])


def test_query_parses_boolean_strings_safely(tmp_path: Path) -> None:
    db_path = tmp_path / "onpe_denorm.db"
    _seed_denorm_like_db(db_path)
    engine = AnalyticsEngine(db_path)

    out = engine.query(
        {
            "dataset": "mesa",
            "election_year": 2026,
            "vuelta": 2,
            "select": ["codigo_mesa", "is_contabilizada"],
            "count_only_contabilizadas": "false",
            "limit": 10,
        }
    )
    assert out["total"] == 5


def test_query_rejects_malformed_where_entries(tmp_path: Path) -> None:
    db_path = tmp_path / "onpe_denorm.db"
    _seed_denorm_like_db(db_path)
    engine = AnalyticsEngine(db_path)

    try:
        engine.query(
            {
                "dataset": "mesa",
                "election_year": 2026,
                "vuelta": 2,
                "select": ["codigo_mesa", "votos"],
                "where": ["invalid"],
            }
        )
        assert False, "Expected ValueError for malformed where"
    except ValueError as exc:
        assert "where" in str(exc)


def test_query_applies_legacy_field_alias_in_where(tmp_path: Path) -> None:
    db_path = tmp_path / "onpe_denorm.db"
    _seed_denorm_like_db(db_path)
    engine = AnalyticsEngine(db_path)

    out = engine.query(
        {
            "dataset": "mesa",
            "election_year": 2026,
            "vuelta": 2,
            "select": ["codigo_mesa", "codigo_estado_acta"],
            "where": [{"field": "codigo_estado_acta", "op": "eq", "value": "C"}],
            "include_special": True,
            "count_only_contabilizadas": False,
            "limit": 20,
        }
    )

    assert out["returned"] == 4
    aliases = out["field_aliases_applied"]
    assert {"from": "codigo_estado_acta", "to": "estado_acta"} in aliases
    assert out["query_echo"]["select"] == ["codigo_mesa", "estado_acta"]
    assert out["query_echo"]["where"][0]["field"] == "estado_acta"


def test_available_catalog_helpers_include_aliases_and_presets(tmp_path: Path) -> None:
    db_path = tmp_path / "onpe_denorm.db"
    _seed_denorm_like_db(db_path)
    engine = AnalyticsEngine(db_path)

    presets = engine.available_presets()
    aliases = engine.available_field_aliases()
    datasets = engine.available_datasets()

    assert "900k_segunda_vuelta_resumen" in presets
    assert aliases["codigo_estado_acta"] == "estado_acta"
    assert "mesa" in datasets
    assert "mesa_num" not in datasets["mesa"]


def test_query_deduplicates_select_after_aliasing(tmp_path: Path) -> None:
    db_path = tmp_path / "onpe_denorm.db"
    _seed_denorm_like_db(db_path)
    engine = AnalyticsEngine(db_path)

    out = engine.query(
        {
            "dataset": "mesa",
            "election_year": 2026,
            "vuelta": 2,
            "select": ["codigo_mesa", "codigo_estado_acta", "estado_acta"],
            "limit": 5,
        }
    )

    assert out["query_echo"]["select"] == ["codigo_mesa", "estado_acta"]
