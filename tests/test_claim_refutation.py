"""Tests para las tools de refutación de claims (1V):
- onpe_estado_actas (1V/2V)
- onpe_margen_pase
- onpe_claim_verifier
- parse_quantitative_claims / classify_claim_topic
"""
from __future__ import annotations

from pathlib import Path

import pytest

from onpe_mcp.storage import DataStore
from onpe_mcp.utils import (
    classify_claim_topic,
    parse_quantitative_claims,
)


# ---------------------------------------------------------------------------
# Fixtures: BD 1V con 3 candidatos + cifras realistas
# ---------------------------------------------------------------------------

@pytest.fixture()
def store_1v(tmp_path: Path) -> DataStore:
    """DataStore con datos 1V sembrados: 3 candidatos + agrupaciones blanco/nulo."""
    store = DataStore(tmp_path)

    # Sembramos 3 mesas en mesas_data con valores que suman a totales conocidos
    # Totales objetivo: padrón 1000, emitidos 800, válidos 600, blancos 150, nulos 50
    rows = [
        # (codigo, ubigeo, electores, emitidos, validos, blancos, nulos, impug, estado)
        ("000001", "150101", 400, 320, 240, 60, 20, 0, "Contabilizada"),
        ("000002", "150102", 300, 240, 180, 45, 15, 0, "Contabilizada"),
        ("000003", "150103", 300, 240, 180, 45, 15, 0, "Contabilizada"),
    ]
    with store._connect() as conn:
        for r in rows:
            conn.execute(
                """INSERT INTO mesas_data
                   (codigo_mesa, ubigeo, local_votacion, electores_habiles,
                    votos_emitidos, votos_validos, blancos, nulos, impugnados,
                    estado_acta, fetched_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (*r[:1], r[1], "LOCAL", *r[2:], "2026-04-13T00:00:00Z"),
            )
        # 3 candidatos en cada mesa: A=100, B=70, C=70 → totales A=300, B=210, C=210=600... wait
        # Necesitamos válidos=600 y queremos margen 2°-3° de 21 (similar a Sánchez-RP)
        # A=300, B=160, C=140 → 300+160+140=600 ✓ y B-C = 20
        # Repartimos por mesa proporcionalmente:
        votes_per_mesa = [
            ("000001", "1", 120),  # FP-like
            ("000001", "2",  64),  # JxP-like (2°)
            ("000001", "3",  56),  # RP-like (3°)
            ("000002", "1",  90),
            ("000002", "2",  48),
            ("000002", "3",  42),
            ("000003", "1",  90),
            ("000003", "2",  48),
            ("000003", "3",  42),
        ]
        for cm, pid, v in votes_per_mesa:
            conn.execute(
                "INSERT INTO votos (codigo_mesa, partido_id, votos, fetched_at) VALUES (?,?,?,?)",
                (cm, pid, v, "2026-04-13T00:00:00Z"),
            )
        agr = [
            ("1", "FUERZA POPULAR"),
            ("2", "JUNTOS POR EL PERÚ"),
            ("3", "RENOVACIÓN POPULAR"),
            ("80", "VOTOS EN BLANCO"),
            ("81", "VOTOS NULOS"),
        ]
        for pid, nom in agr:
            conn.execute(
                "INSERT INTO agrupaciones (partido_id, nombre, fetched_at) VALUES (?,?,?)",
                (pid, nom, "2026-04-13T00:00:00Z"),
            )
        conn.commit()
    return store


# ---------------------------------------------------------------------------
# Tests: get_totales_nacionales_1v
# ---------------------------------------------------------------------------

def test_totales_nacionales_1v(store_1v: DataStore) -> None:
    t = store_1v.get_totales_nacionales_1v()
    assert t["electores_habiles"] == 1000
    assert t["votos_emitidos"] == 800
    assert t["votos_validos"] == 600
    assert t["votos_blancos"] == 150
    assert t["votos_nulos"] == 50
    assert t["participacion_pct"] == 80.0
    assert t["ausentismo_total"] == 200
    assert t["ausentismo_pct"] == 20.0


# ---------------------------------------------------------------------------
# Tests: get_estado_actas_1v
# ---------------------------------------------------------------------------

def test_estado_actas_1v_escrutinio_cerrado(store_1v: DataStore) -> None:
    """En 1V todas las mesas son 'Contabilizada' → escrutinio_cerrado=True."""
    r = store_1v.get_estado_actas_1v()
    assert r["id_eleccion"] == 10
    assert r["escrutinio_cerrado"] is True
    assert r["pct_contabilizadas"] == 100.0
    assert r["totales"]["mesas"] == 3
    assert r["totales"]["contabilizadas_C"] == 3
    assert r["totales"]["observadas_E"] == 0
    assert r["totales"]["pendientes_P"] == 0
    assert r["votos_no_contabilizados"] == []
    assert r["geo_top_no_contabilizadas"] == []


def test_estado_actas_1v_con_observada(tmp_path: Path) -> None:
    """Si alguna mesa quedara Observada, debe contarse aparte de C."""
    store = DataStore(tmp_path)
    with store._connect() as conn:
        conn.execute(
            """INSERT INTO mesas_data
               (codigo_mesa, ubigeo, local_votacion, electores_habiles,
                votos_emitidos, votos_validos, blancos, nulos, impugnados,
                estado_acta, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            ("000001", "150101", "LOCAL", 300, 250, 200, 30, 20, 0,
             "Contabilizada", "2026-04-13T00:00:00Z"),
        )
        conn.execute(
            """INSERT INTO mesas_data
               (codigo_mesa, ubigeo, local_votacion, electores_habiles,
                votos_emitidos, votos_validos, blancos, nulos, impugnados,
                estado_acta, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            ("000002", "150101", "LOCAL", 300, 0, 0, 0, 0, 0,
             "Observada", "2026-04-13T00:00:00Z"),
        )
        conn.commit()
    r = store.get_estado_actas_1v()
    assert r["totales"]["contabilizadas_C"] == 1
    assert r["totales"]["observadas_E"] == 1
    assert r["escrutinio_cerrado"] is False
    assert r["pct_contabilizadas"] == 50.0


# ---------------------------------------------------------------------------
# Tests: get_margen_pase
# ---------------------------------------------------------------------------

def test_margen_pase_por_partido_id(store_1v: DataStore) -> None:
    r = store_1v.get_margen_pase(partido="3", id_eleccion=10)
    assert r["candidato_objetivo"]["partido_id"] == "3"
    assert r["candidato_objetivo"]["nombre"] == "RENOVACIÓN POPULAR"
    assert r["candidato_objetivo"]["posicion"] == 3
    assert r["candidato_objetivo"]["votos"] == 140
    # margen vs anterior (puesto 2)
    assert r["margen_vs_anterior"]["rank"] == 2
    assert r["margen_vs_anterior"]["diferencia_votos"] == 20  # 160 - 140
    # margen vs líder
    assert r["margen_vs_lider"]["rank"] == 1
    assert r["margen_vs_lider"]["diferencia_votos"] == 160  # 300 - 140


def test_margen_pase_por_nombre_alias(store_1v: DataStore) -> None:
    """'lopez aliaga' debe matchear RENOVACIÓN POPULAR via alias."""
    r = store_1v.get_margen_pase(partido="lopez aliaga")
    assert r["candidato_objetivo"]["nombre"] == "RENOVACIÓN POPULAR"


def test_margen_pase_excluye_blanco_y_nulo(store_1v: DataStore) -> None:
    """El ranking de pase NO debe incluir votos en blanco/nulos como competidores."""
    r = store_1v.get_margen_pase(partido="1")
    nombres = [x["nombre"] for x in r["ranking_top"]]
    assert "VOTOS EN BLANCO" not in nombres
    assert "VOTOS NULOS" not in nombres


def test_margen_pase_claim_helper(store_1v: DataStore) -> None:
    """claim_helper debe devolver equivalencias para 1.2% etc."""
    r = store_1v.get_margen_pase(partido="3")
    helper = r["claim_helper"]["1.2%_equivale_a"]
    # 1.2% de padron(1000) = 12 votos
    assert helper["pct_padron_=>_votos"] == 12
    # 1.2% de validos(600) = 7
    assert helper["pct_validos_=>_votos"] == 7


def test_margen_pase_lider_sin_anterior(store_1v: DataStore) -> None:
    """El partido 1 (líder) no tiene margen_vs_anterior ni vs_lider."""
    r = store_1v.get_margen_pase(partido="1")
    assert r["candidato_objetivo"]["posicion"] == 1
    assert r["margen_vs_anterior"] is None
    assert r["margen_vs_lider"] is None


def test_margen_pase_rechaza_sv(store_1v: DataStore) -> None:
    with pytest.raises(ValueError, match="solo aplica a 1V"):
        store_1v.get_margen_pase(partido="3", id_eleccion=11)


def test_margen_pase_partido_inexistente(store_1v: DataStore) -> None:
    with pytest.raises(ValueError, match="no encontrado"):
        store_1v.get_margen_pase(partido="zzz_inexistente")


# ---------------------------------------------------------------------------
# Tests: parse_quantitative_claims
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("phrase,expected_val,expected_unit", [
    ("faltan 900 mil votos", 900_000, "votos"),
    ("son 900 mil votos que no se han contado", 900_000, "votos"),
    ("un millón de peruanos no pudo votar", 1_000_000, "personas"),
    ("más de un millon de votantes", 1_000_000, "votantes"),
    ("cien mil votantes", 100_000, "votantes"),
    ("100 mil electores", 100_000, "electores"),
    ("novecientos mil votos", 900_000, "votos"),
    ("1.2 millones de votos", 1_200_000, "votos"),
    ("miles de actas", None, None),  # "miles" sin número anterior → no parsea
])
def test_parse_absolutos_spanish(phrase: str, expected_val: int | None, expected_unit: str | None) -> None:
    out = parse_quantitative_claims(phrase)
    if expected_val is None:
        assert out["absolutos"] == []
    else:
        assert len(out["absolutos"]) >= 1
        assert any(a["valor"] == expected_val and a["unidad"] == expected_unit
                   for a in out["absolutos"])


@pytest.mark.parametrize("phrase,expected_pct", [
    ("nos restaron 1.2%", 1.2),
    ("perdimos un 1,2 %", 1.2),
    ("ese 1.2 por ciento cambia todo", 1.2),
    ("4 puntos porcentuales", 4.0),
    ("5 pp", 5.0),
])
def test_parse_porcentajes(phrase: str, expected_pct: float) -> None:
    out = parse_quantitative_claims(phrase)
    pcts = [p["valor"] for p in out["porcentajes"]]
    assert expected_pct in pcts


def test_parse_combinado_porcentaje_y_absoluto() -> None:
    """Frase clásica: '1.2% son unos 100 mil votantes'."""
    out = parse_quantitative_claims("nos restaron 1.2% de los votos, unos cien mil votantes")
    pcts = [p["valor"] for p in out["porcentajes"]]
    assert 1.2 in pcts
    vals = [a["valor"] for a in out["absolutos"]]
    assert 100_000 in vals


# ---------------------------------------------------------------------------
# Tests: classify_claim_topic
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("phrase,topic", [
    ("faltan 900 mil votos sin contar", "votos_faltantes"),
    ("hay 900 mil votos desaparecidos", "votos_faltantes"),
    ("un millón no pudo votar", "impedidos_votar"),
    ("más de un millón impedido de votar", "impedidos_votar"),
    ("nos restaron 1.2%", "margen_perdido"),
    ("hay manipulación en miles de actas", "actas_irregulares"),
    ("hola que tal", "general"),
])
def test_classify_claim_topic(phrase: str, topic: str) -> None:
    assert classify_claim_topic(phrase) == topic


# ---------------------------------------------------------------------------
# Smoke tests: server tools end-to-end con store sembrado
# ---------------------------------------------------------------------------

def test_server_tools_smoke(store_1v: DataStore, monkeypatch: pytest.MonkeyPatch) -> None:
    """Las 3 tools nuevas en server.py devuelven la forma esperada."""
    from onpe_mcp import server as srv

    monkeypatch.setattr(srv, "store", store_1v)

    # 1) onpe_estado_actas(id_eleccion=10)
    r1 = srv.onpe_estado_actas(id_eleccion=10)
    assert r1["ok"] is True
    assert r1["data"]["escrutinio_cerrado"] is True
    assert r1["data"]["totales"]["contabilizadas_C"] == 3

    # 2) onpe_margen_pase
    r2 = srv.onpe_margen_pase(partido="3", id_eleccion=10)
    assert r2["ok"] is True
    assert r2["data"]["candidato_objetivo"]["posicion"] == 3
    assert r2["data"]["margen_vs_anterior"]["diferencia_votos"] == 20

    # 3) onpe_claim_verifier — claim clásico "faltan 900 mil votos"
    r3 = srv.onpe_claim_verifier(
        claim_text="Faltan 900 mil votos que no se han contado",
        id_eleccion=10,
    )
    assert r3["ok"] is True
    d = r3["data"]
    assert d["tema_detectado"] == "votos_faltantes"
    assert len(d["veredictos"]) >= 1
    assert d["referencia_oficial"]["padron_habil"] == 1000
    # En este fixture sólo hay 3 mesas y todas son Contabilizadas → claim imposible
    primer_veredicto = d["veredictos"][0]
    assert primer_veredicto["valor_claim"] == 900_000
    assert "veredicto_principal" in primer_veredicto


def test_claim_verifier_rechaza_id_eleccion_no_soportado(store_1v: DataStore, monkeypatch: pytest.MonkeyPatch) -> None:
    from onpe_mcp import server as srv

    monkeypatch.setattr(srv, "store", store_1v)
    r = srv.onpe_claim_verifier(claim_text="faltan 100 mil", id_eleccion=99)
    assert r["ok"] is False
    assert r["errors"][0]["code"] == "INVALID_ARGUMENT"


def test_claim_verifier_inconsistencia_pct_vs_absoluto(store_1v: DataStore, monkeypatch: pytest.MonkeyPatch) -> None:
    """'1.2% son 100 mil' es internamente inconsistente con padrón 1000 (ratios disparatados)."""
    from onpe_mcp import server as srv

    monkeypatch.setattr(srv, "store", store_1v)
    r = srv.onpe_claim_verifier(
        claim_text="nos restaron 1.2%, unos cien mil votantes",
        id_eleccion=10,
    )
    assert r["ok"] is True
    pct_verdicts = [v for v in r["data"]["veredictos"] if v["tipo"] == "porcentaje"]
    assert pct_verdicts
    # Debe detectar inconsistencia interna
    assert pct_verdicts[0]["inconsistencia_con_absoluto"] is not None


def test_estado_actas_rechaza_id_eleccion_invalido(store_1v: DataStore, monkeypatch: pytest.MonkeyPatch) -> None:
    from onpe_mcp import server as srv

    monkeypatch.setattr(srv, "store", store_1v)
    r = srv.onpe_estado_actas(id_eleccion=99)
    assert r["ok"] is False
    assert r["errors"][0]["code"] == "INVALID_ARGUMENT"
