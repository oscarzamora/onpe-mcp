"""Cycle 86: candidatos-con-mas-votos geo fix, tercer/segundo mas votado, mesas escrutadas, historical."""
import pytest
from onpe_mcp.server import onpe_chat


def intent(q):
    return onpe_chat(q)["data"]["intent"]


# ── Grupo 1: "candidatos con mas votos en X" → geo_domestic ───────────────────
def test_c86_candidatos_mas_votos_lima():
    assert intent("candidatos con mas votos en lima") == "geo_domestic"


def test_c86_candidatos_mas_votos_arequipa():
    assert intent("candidatos con mas votos en arequipa") == "geo_domestic"


def test_c86_candidatos_mas_votos_ica():
    # "ica" es solo 3 chars; la corrección de {4,} → {3,} hace que esto funcione
    assert intent("candidatos con mas votos en ica") == "geo_domestic"


def test_c86_candidatos_mas_votos_tacna():
    assert intent("candidatos con mas votos en tacna") == "geo_domestic"


def test_c86_candidatos_mas_votos_madre_de_dios():
    assert intent("candidatos con mas votos en madre de dios") == "geo_domestic"


def test_c86_candidatos_mas_votados_puno():
    assert intent("candidatos mas votados en puno") == "geo_domestic"


def test_c86_candidatos_mas_votados_loreto():
    assert intent("candidatos mas votados en loreto") == "geo_domestic"


def test_c86_candidatos_mas_votados_cusco():
    assert intent("candidatos mas votados en cusco") == "geo_domestic"


# ── Grupo 2: "candidatos con mas votos" sin geo → nacional ────────────────────
def test_c86_candidatos_mas_votos_sin_geo():
    assert intent("candidatos con mas votos") == "nacional"


def test_c86_quienes_son_los_mas_votados():
    assert intent("quienes son los mas votados") == "nacional"


def test_c86_lista_candidatos_mas_votados():
    assert intent("lista de candidatos mas votados") == "nacional"


# ── Grupo 3: "tercer/segundo candidato mas votado" → nacional ─────────────────
def test_c86_tercer_candidato_mas_votado():
    assert intent("cual fue el tercer candidato mas votado") == "nacional"


def test_c86_segundo_candidato_mas_votado():
    assert intent("quien fue el segundo candidato mas votado") == "nacional"


def test_c86_cuarto_candidato_mas_votado():
    assert intent("cual es el cuarto candidato mas votado") == "nacional"


# ── Grupo 4: "el mas votado" / "segundo mas votado" → nacional ────────────────
def test_c86_el_segundo_mas_votado():
    assert intent("el segundo mas votado") == "nacional"


def test_c86_quien_resulto_mas_votado():
    assert intent("quien resulto mas votado") == "nacional"


def test_c86_el_mas_votado():
    assert intent("el mas votado") == "nacional"


def test_c86_tercer_mas_votado():
    assert intent("tercer mas votado") == "nacional"


def test_c86_segundo_mas_votado_nacional():
    assert intent("segundo mas votado a nivel nacional") == "nacional"


def test_c86_candidato_mas_votado_nacional():
    assert intent("el candidato mas votado a nivel nacional") == "nacional"


def test_c86_cuantos_votos_candidato_mas_votado():
    assert intent("cuantos votos tiene el candidato mas votado") == "nacional"


def test_c86_el_mas_votado_en_el_pais():
    assert intent("el mas votado en el pais") == "nacional"


# ── Grupo 5: "el mas votado en X" → geo_domestic ─────────────────────────────
def test_c86_el_mas_votado_en_puno():
    assert intent("el mas votado en puno") == "geo_domestic"


def test_c86_los_mas_votados_en_lima():
    assert intent("los mas votados en lima") == "geo_domestic"


def test_c86_votados_en_lima():
    assert intent("votados en lima") == "geo_domestic"


# ── Grupo 6: mesas escrutadas / porcentaje escrutinio → nacional ──────────────
def test_c86_total_mesas_escrutadas():
    assert intent("total de mesas escrutadas") == "nacional"


def test_c86_porcentaje_mesas_contadas():
    assert intent("porcentaje de mesas contadas") == "nacional"


def test_c86_cuantas_mesas_escrutadas():
    assert intent("cuantas mesas escrutadas hay") == "nacional"


def test_c86_porcentaje_mesas_escrutadas():
    assert intent("que porcentaje de mesas se han escrutado") == "nacional"


def test_c86_porcentaje_escrutinio_actual():
    assert intent("porcentaje de escrutinio actual") == "nacional"


def test_c86_cuantas_mesas_procesadas():
    assert intent("cuantas mesas procesadas") == "nacional"


def test_c86_total_votos_escrutados():
    assert intent("total de votos escrutados") == "nacional"


def test_c86_mesas_escrutadas_en_lima():
    # Mesas escrutadas en un dept → nacional (DB no filtra por dept para este stat)
    assert intent("mesas escrutadas en lima") == "nacional"


# ── Grupo 7: preguntas históricas → unknown ───────────────────────────────────
def test_c86_primera_eleccion_presidencial():
    assert intent("cual fue la primera eleccion presidencial del peru") == "unknown"


def test_c86_primer_candidato_presidencia():
    assert intent("quien fue el primer candidato a la presidencia del peru") == "unknown"


def test_c86_primera_eleccion_en_peru():
    assert intent("primera eleccion presidencial en peru") == "unknown"


def test_c86_primer_presidente():
    assert intent("quien fue el primer presidente del peru") == "unknown"


# ── Grupo 8: varios ───────────────────────────────────────────────────────────
def test_c86_sufragios_mendoza_lima():
    # "mendoza" es ciudad argentina → geo (ambiguo pero aceptable)
    assert intent("cuantos sufragios obtuvo mendoza en lima") == "geo"


def test_c86_candidatos_mas_votos_piura():
    assert intent("candidatos con mas votos en piura") == "geo_domestic"


def test_c86_candidatos_mas_votos_junin():
    assert intent("candidatos con mas votos en junin") == "geo_domestic"
