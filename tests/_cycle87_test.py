"""Cycle 87: sufragios patterns, votacion geo, resultado de la votacion, GEO_IN_Q exclusions."""
import pytest
from onpe_mcp.server import onpe_chat


def intent(q):
    return onpe_chat(q)["data"]["intent"]


# ── Grupo 1: "resultado(s) de la votacion en X" → geo_domestic ───────────────
def test_c87_resultado_votacion_callao():
    assert intent("resultado de la votacion en callao") == "geo_domestic"


def test_c87_resultado_votacion_lima():
    assert intent("resultado de la votacion en lima") == "geo_domestic"


def test_c87_resultados_votacion_arequipa():
    assert intent("resultados de la votacion en arequipa") == "geo_domestic"


def test_c87_resultados_votaciones_piura():
    assert intent("resultados de las votaciones en piura") == "geo_domestic"


def test_c87_resultado_votacion_moquegua():
    assert intent("resultado de la votacion en moquegua") == "geo_domestic"


# ── Grupo 2: "resultado(s) de la votacion" sin geo → nacional ─────────────────
def test_c87_resultado_votacion_sin_geo():
    assert intent("resultado de la votacion") == "nacional"


def test_c87_resultados_votacion_sin_geo():
    assert intent("resultados de la votacion") == "nacional"


def test_c87_resultados_votaciones_sin_geo():
    assert intent("resultados de las votaciones") == "nacional"


# ── Grupo 3: sufragios de candidato → candidate ───────────────────────────────
def test_c87_sufragios_obtenidos_aliaga():
    assert intent("sufragios obtenidos por aliaga") == "candidate"


def test_c87_sufragios_de_fujimori_lima():
    assert intent("sufragios de fujimori en lima") == "candidate"


def test_c87_sufragios_de_aliaga_tacna():
    assert intent("sufragios de aliaga en tacna") == "candidate"


def test_c87_sufragios_de_nieto_loreto():
    assert intent("sufragios de nieto en loreto") == "candidate"


def test_c87_sufragios_obtenidos_nieto_lima():
    assert intent("sufragios obtenidos por nieto en lima") == "candidate"


def test_c87_sufragios_logrados_keiko_arequipa():
    assert intent("sufragios logrados por keiko en arequipa") == "candidate"


def test_c87_cuantos_sufragios_obtuvo_aliaga():
    assert intent("cuantos sufragios obtuvo aliaga") == "candidate"


def test_c87_sufragios_de_aliaga():
    assert intent("sufragios de aliaga") == "candidate"


def test_c87_sufragios_fujimori_ica():
    assert intent("sufragios de fujimori en ica") == "candidate"


# ── Grupo 4: sufragios estadísticos → nacional ────────────────────────────────
def test_c87_sufragios_validos():
    assert intent("sufragios validos") == "nacional"


def test_c87_sufragios_totales():
    assert intent("sufragios totales") == "nacional"


def test_c87_sufragios_emitidos():
    assert intent("sufragios emitidos") == "nacional"


def test_c87_sufragios_validos_en_total():
    assert intent("sufragios validos en total") == "nacional"


def test_c87_total_sufragios_validos():
    assert intent("total de sufragios validos") == "nacional"


def test_c87_total_sufragios_por_candidato():
    assert intent("total de sufragios por candidato") == "nacional"


# ── Grupo 5: "quien gano la votacion" → nacional/geo ─────────────────────────
def test_c87_quien_gano_la_votacion():
    assert intent("quien gano la votacion") == "nacional"


def test_c87_quien_gano_votacion_arequipa():
    assert intent("quien gano la votacion en arequipa") == "geo_domestic"


def test_c87_quien_gano_votacion_lima():
    assert intent("quien gano la votacion en lima") == "geo_domestic"


def test_c87_quien_gano_eleccion():
    assert intent("quien gano la eleccion") == "nacional"


# ── Grupo 6: sufragios en dept → geo_domestic ────────────────────────────────
def test_c87_sufragios_en_puno():
    assert intent("los sufragios en puno") == "geo_domestic"


def test_c87_sufragios_en_cusco():
    assert intent("los sufragios en cusco") == "geo_domestic"


def test_c87_votaciones_en_cusco():
    assert intent("votaciones en cusco") == "geo_domestic"


# ── Grupo 7: misc ─────────────────────────────────────────────────────────────
def test_c87_sufragios_nulos():
    assert intent("sufragios nulos cuantos hay") == "nacional"


def test_c87_cuantos_sufragios_en_total():
    assert intent("cuantos sufragios en total") == "nacional"


def test_c87_quien_gano_en_trujillo():
    assert intent("quien gano en trujillo") == "geo_domestic"
